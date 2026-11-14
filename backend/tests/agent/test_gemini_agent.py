"""The agent loop with a scripted Gemini: each turn is the tool calls Gemini "decides" on."""

from types import SimpleNamespace

import pytest
from google.genai import types

import core.briefs as briefs
import core.competitors as competitors
from agent import gemini_agent, tools
from contracts.schemas import Competitor
from core.competitors import Judgement
from data import get_store

STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"


class Script:
    """Stands in for genai.Client. A turn is a list of (tool, args), or a function of the
    conversation so far that returns one (to use what the last tool result said)."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.seen = []  # per call: (allowed tool names, the conversation so far)
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        allowed = config.tool_config.function_calling_config.allowed_function_names
        self.seen.append((allowed, list(contents)))
        turn = self.turns.pop(0)
        turn = turn(contents) if callable(turn) else turn
        calls = [types.FunctionCall(name=n, args=a) for n, a in turn]
        content = types.Content(role="model", parts=[types.Part(function_call=c) for c in calls])
        return SimpleNamespace(function_calls=calls, candidates=[SimpleNamespace(content=content)])

    def results(self) -> list[dict]:
        """Every tool result Gemini was sent, in order."""
        return [
            p.function_response.response
            for c in self.seen[-1][1]
            for p in c.parts
            if p.function_response
        ]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Fake store; Stendr's one direct competitor is Kelluu; briefs written by a fixed draft."""
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    monkeypatch.setenv("GEMINI_MODEL_FAST", "test-model")
    get_store.cache_clear()

    async def fake_judge(company, graph):
        store = get_store()
        direct = [Competitor(company=await store.company(KELLUU), reason="both fly")]
        space = [c for c in await store.candidate_competitors(company) if c.id != KELLUU]
        return Judgement(direct=direct, space=space)

    async def fake_draft(prompt, schema, **kw):
        return schema.model_validate(
            {"sections": [{"heading": "Verdict", "sentences": [{"text": "Fits.", "facts": [2]}]}]}
        )

    monkeypatch.setattr(competitors, "cached_judge", fake_judge)
    monkeypatch.setattr(competitors, "_graph", object())
    monkeypatch.setattr(competitors, "_memo", {})
    monkeypatch.setattr(briefs, "structured", fake_draft)
    yield
    get_store.cache_clear()


async def collect(stream):
    return [event async for event in stream]


async def stendr():
    return await get_store().company(STENDR)


async def test_slush_prep_one_brief_one_error_then_done():
    def script(name):
        if name == "Maki.vc":
            return [
                [("resolve_company", {"name": "Maki.vc", "kind": "investor"})],
                [("investor_brief", {"investor_id": MAKI})],
            ]
        return [
            [("resolve_company", {"name": name, "kind": "investor"})],
            [("investor_brief", {"investor_id": "made-up-id"})],  # not from resolve -> refused
            [("give_up", {"reason": f'No investor named "{name}" found in Cala'})],
        ]

    class PerInvestor:  # the two investors run in parallel: route each call to its own script
        def __init__(self):
            self.scripts = {n: Script(*script(n)) for n in ("Maki.vc", "Nonexistent Capital")}
            self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

        async def _generate(self, *, model, contents, config):
            name = next(n for n in self.scripts if f'"{n}"' in contents[0].parts[0].text)
            return await self.scripts[name]._generate(model=model, contents=contents, config=config)

    client = PerInvestor()
    pasted = ["Maki.vc", "Nonexistent Capital", "Maki.vc", " "]  # a repeat and a blank: ignored
    events = await collect(gemini_agent.slush_prep(await stendr(), pasted, client=client))

    assert events[0].type == "step" and events[0].investor_name is None
    assert events[-1].type == "done" and [e.type for e in events].count("done") == 1
    maki = [e for e in events if e.investor_name == "Maki.vc"]
    assert [e.type for e in maki] == ["step", "step", "brief"]
    assert maki[0].investor is None and maki[1].investor.id == MAKI
    assert maki[2].brief.investor_id == MAKI and maki[2].brief.company_id == STENDR
    assert maki[2].brief.citations and "[1]" in maki[2].brief.markdown
    nobody = [e for e in events if e.investor_name == "Nonexistent Capital"]
    assert [e.type for e in nobody] == ["step", "error"]
    assert "Nonexistent Capital" in nobody[1].message
    assert "unknown id" in client.scripts["Nonexistent Capital"].results()[1]["error"]


async def test_chat_cites_facts_and_drops_what_they_do_not_back():
    def answer(contents):  # cite the conflict fact by the number the tool result gave it
        facts = contents[-1].parts[0].function_response.response["facts"]
        n = int(facts[0].split(".")[0])
        sentences = [
            {"text": "Skip NATO Innovation Fund: it backs Kelluu.", "facts": [n]},
            {"text": "It manages 1 billion euros.", "facts": [n]},  # number not in the fact
            {"text": "Everyone loves them.", "facts": []},  # cites nothing
        ]
        return [("answer", {"sentences": sentences})]

    client = Script(
        [("resolve_company", {"name": "NATO Innovation Fund", "kind": "investor"})],
        [("check_conflict", {"investor_id": NIF, "company_id": STENDR})],
        answer,
    )
    events = await collect(gemini_agent.chat("Should I pitch NIF?", await stendr(), client=client))

    assert [e.type for e in events] == ["step", "step", "text", "done"]
    assert events[1].message == "Checking NATO Innovation Fund for conflicts with Stendr"
    assert events[2].message.startswith("Skip NATO Innovation Fund: it backs Kelluu. [1]")
    assert events[-1].citations and events[-1].citations[0].url
    first_prompt = client.seen[0][1][0].parts[0].text
    assert STENDR in first_prompt and "Should I pitch NIF?" in first_prompt


async def test_chat_refuses_unknown_ids_and_says_so_when_nothing_is_sourced():
    unsourced = [("answer", {"sentences": [{"text": "They raised a lot.", "facts": [7]}]})]
    client = Script([("get_rounds", {"company_id": "made-up-id"})], unsourced, unsourced)
    events = await collect(gemini_agent.chat("How much did X raise?", client=client))
    assert [e.type for e in events] == ["text", "done"]
    assert events[0].message.startswith(gemini_agent.NOTHING) and events[1].citations == []
    assert "unknown id" in client.results()[0]["error"]


async def test_budget_spent_only_the_closing_tool_is_allowed():
    async def ask(args):
        yield {"facts": []}

    async def never_good(args):
        yield {"error": "try again"}

    toolbox = [(tools.sourced_answer, ask), (gemini_agent.answer, never_good)]
    question = [("sourced_answer", {"question": "Who led Kelluu's Series A?"})]
    close = [("answer", {"sentences": []})]
    client = Script(question, question, close, close)
    events = await collect(
        gemini_agent.loop("s", "p", toolbox, closing="answer", max_calls=2, client=client)
    )
    assert [allowed for allowed, _ in client.seen] == [None, None, ["answer"], ["answer"]]
    assert events[-1].type == "error" and "ran out of steps" in events[-1].message


async def test_gemini_down_is_an_error_event_then_done(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FAST", "")
    monkeypatch.setenv("GEMINI_MODEL_SMART", "")  # .env may have set it
    events = await collect(gemini_agent.chat("hi", client=Script()))
    assert [e.type for e in events] == ["error", "done"]
    assert "GEMINI_MODEL_FAST" in events[0].message
