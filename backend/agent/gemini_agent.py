"""Gemini agent (B13-B14): a function-calling loop over agent/tools.py.

Gemini only chooses which tool to call next and words the result. What it may say comes from the
tools: slush prep ends in `investor_brief` (cited by core/briefs.py), chat ends in `answer`, whose
sentences cite numbered facts that the code turns into [n] markers (uncited sentences are dropped).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable

from google.genai import types
from pydantic import ValidationError, validate_call

from agent import tools
from agent.llm import LLMError, generate
from contracts.schemas import AgentEvent, Company, EntityRef, Reason, Source
from core.briefs import Sentence, cited
from core.competitors import stored_judgement
from data import DataError

MAX_CALLS = 12  # tool calls per agent run; after that only the closing tool is allowed
CLOSING_TRIES = 2  # extra turns to get a usable closing call before the run gives up
SLUSH_MAX_CALLS = 5  # per pasted investor: look up, maybe retry a spelling, brief
SLUSH_PARALLEL = 3  # pasted investors worked on at once

log = logging.getLogger("agent")

# A handler runs one tool call. It yields the events the user sees and, at most once, a dict:
# the result Gemini reads next. Ending without a dict ends the run.
Handler = Callable[[dict], AsyncIterator["AgentEvent | dict"]]

CHAT_TOOLS = [
    tools.resolve_company,
    tools.find_competitors,
    tools.get_rounds,
    tools.investor_profile,
    tools.check_conflict,
    tools.rank_investors,
    tools.sourced_answer,
]
STEPS = {
    "resolve_company": "Looking up {name} in Cala",
    "find_competitors": "Finding {company}'s direct competitors",
    "get_rounds": "Reading {company}'s funding rounds in Cala",
    "investor_profile": "Reading {investor}'s rounds and portfolio in Cala",
    "check_conflict": "Checking {investor} for conflicts with {company}",
    "rank_investors": "Ranking investors for {company}",
    "sourced_answer": "Asking Cala: {question}",
}


def _step(message: str) -> AgentEvent:
    return AgentEvent(type="step", message=message)


def _with_calls(resp):
    if not resp.function_calls:
        raise ValueError("Gemini answered without a tool call")
    return resp


async def loop(
    system: str,
    prompt: str,
    toolbox: list[tuple[Callable, Handler]],
    *,
    closing: str,
    max_calls: int = MAX_CALLS,
    client=None,
) -> AsyncIterator[AgentEvent]:
    """Let Gemini call tools until a handler ends the run. Each pair is (the function whose
    signature and docstring Gemini sees, the handler that runs the call)."""
    handlers = {fn.__name__: handler for fn, handler in toolbox}
    declared = types.Tool(function_declarations=[tools.declaration(fn) for fn, _ in toolbox])
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    used = 0
    while used < max_calls + CLOSING_TRIES:
        allowed = [closing] if used >= max_calls else None
        config = types.GenerateContentConfig(
            temperature=0,
            system_instruction=system,
            tools=[declared],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=allowed
                )
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            resp = await generate(contents, config, _with_calls, tier="smart", client=client)
        except LLMError as exc:
            yield AgentEvent(type="error", message=f"The agent is unavailable: {exc}")
            return
        contents.append(resp.candidates[0].content)  # as sent: keeps Gemini's thought signatures
        results = []
        for call in resp.function_calls:
            used += 1
            result = None
            if call.name not in handlers or (allowed and call.name not in allowed):
                result = {"error": f"tool {call.name!r} is not available now"}
            else:
                try:
                    async for item in handlers[call.name](dict(call.args or {})):
                        if isinstance(item, AgentEvent):
                            yield item
                        else:
                            result = item
                except (DataError, LLMError, ValidationError) as exc:
                    result = {"error": str(exc) or type(exc).__name__}
                if result is None:
                    return
            results.append(types.Part.from_function_response(name=call.name, response=result))
        contents.append(types.Content(role="user", parts=results))
    yield AgentEvent(type="error", message="The agent ran out of steps before finishing.")


# --- slush prep: one brief per pasted investor --------------------------------------------------

SLUSH_SYSTEM = """You prepare a startup founder for a meeting with one investor, whose name the \
founder pasted. Work in this order:
1. Call resolve_company with the pasted name and kind "investor".
2. Pick the match that is this investor: a venture fund, investment firm or other investor. \
Judge by type and description; a company that only shares the name is the wrong match. If there \
is no match, try once more with a plainer spelling (drop words like "Ventures", "Capital", \
"Oy", "AB", or a trailing ".vc").
3. Call investor_brief with the id of the match.
Call give_up instead when nothing matches, when no match is an investor, or when several matches \
fit equally well and you cannot tell which one is meant. Its reason is one short sentence for the \
founder. Only use ids that resolve_company returned."""


async def investor_brief(investor_id: str) -> None:
    """Write the brief on this investor for the founder. This finishes the job."""


async def give_up(reason: str) -> None:
    """Stop without a brief. `reason`: one short sentence for the founder, e.g. 'No investor
    named "X" found in Cala' or 'Several investors are called "X": ...'."""


async def prep_one(name: str, company: Company, *, client=None) -> AsyncIterator[AgentEvent]:
    """The events for one pasted investor name, ending in a `brief` or an `error` event."""
    seen: dict[str, EntityRef] = {}
    investor: EntityRef | None = None

    async def resolve(args: dict):
        yield _step(f"Looking up {args.get('name')} in Cala")
        found = await validate_call(tools.resolve_company)(**args)
        seen.update({ref.id: ref for ref in found})
        yield {"matches": [ref.model_dump() for ref in found]}

    async def brief(args: dict):
        nonlocal investor
        ref = seen.get(str(args.get("investor_id")))
        if ref is None:
            yield {"error": "unknown id: use an id that resolve_company returned"}
            return
        investor = ref
        yield _step(f"Found {ref.name}. Checking conflicts and recent rounds")
        try:
            done = await tools.investor_brief(ref.id, company.id)
        except DataError as exc:
            yield {"error": f"no brief possible for this match: {exc}"}
            return
        yield AgentEvent(type="brief", brief=done)

    async def stop(args: dict):
        reason = str(args.get("reason") or "").strip()
        reason = reason or f'No investor named "{name}" found in Cala'
        yield AgentEvent(type="error", message=reason)

    toolbox = [(tools.resolve_company, resolve), (investor_brief, brief), (give_up, stop)]
    prompt = f'Pasted investor name: "{name}"\nThe founder\'s company: {company.name}'
    events = loop(
        SLUSH_SYSTEM, prompt, toolbox, closing="give_up", max_calls=SLUSH_MAX_CALLS, client=client
    )
    async for event in events:
        yield event.model_copy(update={"investor_name": name, "investor": investor})


async def _slush(company: Company, names: list[str], client) -> AsyncIterator[AgentEvent]:
    yield _step(f"Finding {company.name}'s direct competitors")
    await stored_judgement(company)  # once, before the investors need it in parallel

    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    gate = asyncio.Semaphore(SLUSH_PARALLEL)

    async def one(name: str) -> None:
        try:
            async with gate:
                async for event in prep_one(name, company, client=client):
                    queue.put_nowait(event)
        except Exception as exc:  # one investor failing must not end the others
            log.exception("slush prep failed for %r", name)
            failed = AgentEvent(type="error", message=f"Could not prepare this one: {exc}")
            queue.put_nowait(failed.model_copy(update={"investor_name": name}))
        finally:
            queue.put_nowait(None)

    tasks = [asyncio.create_task(one(name)) for name in names]
    try:
        for _ in tasks:
            while (event := await queue.get()) is not None:
                yield event
    finally:
        for task in tasks:
            task.cancel()


def slush_prep(company: Company, names: list[str], *, client=None) -> AsyncIterator[AgentEvent]:
    """One brief (or one error) per pasted investor name, a few at a time; ends with `done`.
    Events of different investors interleave; each carries its `investor_name`."""
    pasted = list(dict.fromkeys(n for n in names if n.strip()))
    return _closed(_slush(company, pasted, client), list)


# --- chat ---------------------------------------------------------------------------------------

CHAT_SYSTEM = """You answer questions from a startup founder or an investor about investors, \
competitors and funding rounds, using Pitchlist's tools over Cala's data.
Tools return numbered facts and the ids of the entities in them. Use ids only as tool arguments; \
never show an id. A conflict means an investor backs a direct competitor; rank_investors gives \
who to pitch and who to skip; check_conflict answers "should I pitch this investor?".
Finish by calling `answer`, alone, after you have read the facts you need. Every sentence of the \
answer cites the one or two facts that most directly support it and says only what those facts \
say. Copy names, numbers and dates exactly; never compute, round or add knowledge of your own. \
Lead with the direct answer; at most 6 short, plain sentences. If the facts do not answer the \
question, say what is missing in a sentence that cites the closest fact."""

NOTHING = (
    "I couldn't find sourced facts in Cala to answer that. Try asking about a company's "
    "investors, competitors or funding rounds."
)


async def answer(sentences: list[Sentence]) -> list[Sentence]:
    """Give the final answer. Each sentence lists in `facts` the numbers of the one or two
    facts it rests on. This finishes the conversation turn."""
    return sentences


async def _chat(
    message: str,
    company: Company | None,
    investor: Company | None,
    citations: list[Source],
    client,
) -> AsyncIterator[AgentEvent]:
    names = {e.id: e.name for e in (company, investor) if e}  # every entity seen: id -> name
    facts: list[Reason] = []
    tries = 0

    def data(fn: Callable) -> Handler:
        async def handle(args: dict):
            ids = [v for k, v in args.items() if k.endswith("_id")]
            if any(i not in names for i in ids):
                yield {"error": "unknown id: use an id from the context or from a tool result"}
                return
            label = STEPS[fn.__name__].format(
                name=args.get("name"),
                question=args.get("question"),
                company=names.get(args.get("company_id", ""), "the company"),
                investor=names.get(args.get("investor_id", ""), "the investor"),
            )
            yield _step(label)
            result = await validate_call(fn)(**args)
            new_names = tools.names_in(result)
            names.update(new_names)
            if fn is tools.resolve_company:
                yield {"matches": [ref.model_dump() for ref in result]}
                return
            new = tools.facts(fn.__name__, args, result, names)
            numbered = [f"{len(facts) + i}. {f.text}" for i, f in enumerate(new, 1)]
            facts.extend(new)
            mentioned = {i: n for i, n in new_names.items() if any(n in f.text for f in new)}
            yield {"facts": numbered or "nothing found", "entities": mentioned}

        return handle

    async def finish(args: dict):
        nonlocal tries
        tries += 1
        lines = cited(await validate_call(answer)(**args), facts, citations)
        if not lines and tries == 1:
            yield {"error": "No sentence cited a fact number you were given. Call tools first, "
                   "then answer with sentences that each cite one or two fact numbers."}
            return
        for line in lines or [NOTHING]:
            yield AgentEvent(type="text", message=line + " ")

    scope = [
        f"The founder's company: {company.name} (id {company.id})" if company else "",
        f"The investor in view: {investor.name} (id {investor.id})" if investor else "",
    ]
    prompt = "\n".join([*filter(None, scope), f"Question: {message}"])
    toolbox = [*((fn, data(fn)) for fn in CHAT_TOOLS), (answer, finish)]
    async for event in loop(CHAT_SYSTEM, prompt, toolbox, closing="answer", client=client):
        yield event


def chat(
    message: str,
    company: Company | None = None,
    investor: Company | None = None,
    *,
    client=None,
) -> AsyncIterator[AgentEvent]:
    """`step` events while tools run, the answer as `text` events with [n] markers, then `done`
    carrying the citations the markers point into."""
    citations: list[Source] = []
    return _closed(_chat(message, company, investor, citations, client), lambda: citations)


async def _closed(
    events: AsyncIterator[AgentEvent], citations: Callable[[], list[Source]]
) -> AsyncIterator[AgentEvent]:
    """`events`, then `done`, whatever happens: once a stream has started, a failure can only be
    told as an `error` event."""
    try:
        async for event in events:
            yield event
    except Exception as exc:
        log.exception("agent run failed")
        yield AgentEvent(type="error", message=f"Something went wrong: {exc}")
    yield AgentEvent(type="done", citations=citations())
