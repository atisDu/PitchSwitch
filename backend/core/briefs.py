"""investor_brief (B11): a one-page, fully cited brief on one investor for one company.

Facts come only from the store (and Cala's sourced answer); each fact carries its sources.
Gemini only writes sentences that cite fact numbers. The code then renders the markdown and the
[n] markers, and drops any sentence that cites nothing valid or holds a number its facts don't.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

from pydantic import BaseModel

from agent.llm import LLMError, structured
from contracts.schemas import Brief, Company, Competitor, Conflict, Reason, Round, Source
from core.competitors import judge
from core.conflict import check_conflict
from core.xray import hidden_rivals
from data import NotFound, get_store

BRIEFS = "briefs"  # graph collection: one brief per (store, investor, company, facts)
MAX_ROUNDS = 8  # most recent rounds of the investor shown as facts
MAX_ANSWER_CLAIMS = 8
MAX_SOURCES_PER_FACT = 3  # best-ranked first
MAX_FACTS_PER_SENTENCE = 2
_RANK = {"PRIMARY": 0, "FILING": 1, "PRESS": 2, "AGGREGATOR": 3, "UNKNOWN": 4}

SYSTEM = """You write a one-page brief for a startup founder about one investor: should they \
pitch this investor, and what should they know first. Use ONLY the numbered facts given; never \
add knowledge of your own. Every sentence cites the one or two facts that most directly support \
it. Copy numbers, dates and names exactly as the facts give them; never compute or round.
Only facts that start with "Conflict:" are conflicts. If there is one, the verdict says to skip \
this investor and why. If there is none, the verdict says no conflict was found and leave out the \
Conflicts section; backing companies in the same market is relevant experience, not a conflict.
Never state two versions of the same thing (one round called Pre-Seed in one sentence and Seed \
in another, two amounts or dates for it). Use the most specific fact about that round and leave \
the other version out; a summary that lists several companies' rounds is less specific than a \
fact about one round, and a general word ("seed rounds") is not a disagreement. Only when two \
equally specific facts give different amounts or dates for the same round, write one sentence \
that says the sources differ and cites both. Do not look for disagreements beyond that.
Sections, in order, skipping any without facts: "Verdict", "Fit with <company>", \
"Recent activity", "Conflicts". Use each fact in one section only. At most 12 sentences in all. \
Short, plain sentences; no marketing language."""

log = logging.getLogger("core.briefs")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


class Sentence(BaseModel):
    text: str
    facts: list[int]  # 1-based fact numbers


class _Section(BaseModel):
    heading: str
    sentences: list[Sentence]


class _Draft(BaseModel):
    sections: list[_Section]


def _sector(company: Company) -> str:
    tag = next((i for i in company.industries if i != "SOFTWARE_AND_SERVICES"), None)
    tag = tag or (company.industries[0] if company.industries else "")
    return tag.replace("_AND_", " and ").replace("_", " ").lower() or "startup"


def round_fact(rd: Round, investor_id: str, names: dict[str, str]) -> str:
    who = names.get(rd.company_id, "a company")
    led = next((ri.is_lead for ri in rd.investors if ri.investor.id == investor_id), None)
    role = "Led" if led else "Took part in"
    parts = [f"{role} {who}'s {rd.label or 'round'}"]
    if rd.amount_text:
        parts.append(f"of {rd.amount_text}")
    if rd.date:
        parts.append(f"on {rd.date}")
    return " ".join(parts)


async def company_names(ids: list[str], known: dict[str, str]) -> dict[str, str]:
    """`known` plus the names of the `ids` it lacks (looked up; unknown ids stay out)."""
    store = get_store()
    missing = list({i for i in ids if i not in known})
    found = await asyncio.gather(*(store.company(i) for i in missing), return_exceptions=True)
    pairs = zip(missing, found, strict=True)
    return known | {i: c.name for i, c in pairs if isinstance(c, Company)}


def conflict_fact(c: Conflict, investor: str, company: str) -> Reason:
    via = f" through {c.via_person.name}, who sits on its board" if c.via_person else ""
    return Reason(
        text=f"Conflict: {investor} backs {c.competitor.name}{via}, a direct competitor of "
        f"{company}.",
        sources=c.sources,
    )


def best_sources(fact: Reason) -> Reason:
    """The fact with its best-ranked sources only (Cala claims can carry 15+ documents)."""
    top = sorted(fact.sources, key=lambda x: _RANK[x.rank])[:MAX_SOURCES_PER_FACT]
    return fact.model_copy(update={"sources": top})


async def collect_facts(
    investor_id: str,
    company: Company,
    competitors: list[Competitor],
    space: list[Company],
) -> tuple[str, list[Reason]]:
    """The investor's name and every sourced fact the brief may use (facts without sources are
    left out: they could not be cited)."""
    store = get_store()
    investor = await store.company(investor_id)
    question = (
        f"Which {_sector(company)} companies has {investor.name} invested in, "
        f"and which rounds did it lead?"
    )
    # Cala's search (the slow part, up to a minute uncached) runs alongside the rest.
    async def conflicts_with_hidden() -> list[Conflict]:
        hidden = await hidden_rivals(company, investor.id, competitors, space)
        return await check_conflict(investor.id, competitors, hidden=hidden)

    conflicts, rounds, portfolio, (_, claims) = await asyncio.gather(
        conflicts_with_hidden(),
        store.investor_rounds(investor.id),
        store.portfolio(investor.id),
        store.sourced_answer(question),
    )

    names = {link.company.id: link.company.name for link in portfolio}
    names |= {c.id: c.name for c in space} | {c.company.id: c.company.name for c in competitors}
    recent = sorted(rounds, key=lambda r: r.date or "", reverse=True)[:MAX_ROUNDS]
    names = await company_names([rd.company_id for rd in recent], names)

    facts: list[Reason] = [
        Reason(
            text=f"{company.name}: {company.description or 'no description'}"
            + (f" Stage: {company.stage}." if company.stage else ""),
            sources=company.sources,
        ),
        Reason(
            text=f"{investor.name}: {investor.description or 'no description'}",
            sources=investor.sources,
        ),
    ]
    facts += [conflict_fact(c, investor.name, company.name) for c in conflicts]
    in_space = {c.id for c in space} | {c.company.id for c in competitors}
    for link in portfolio:
        if link.company.id in in_space and link.company.id not in {
            c.competitor.id for c in conflicts
        }:
            facts.append(
                Reason(
                    text=f"{investor.name} has backed {link.company.name}, which works in the same "
                    f"market as {company.name} but is not a direct competitor (no conflict).",
                    sources=link.sources,
                )
            )
    facts += [Reason(text=round_fact(rd, investor.id, names), sources=rd.sources) for rd in recent]
    facts += [Reason(text=f"Cala: {r.text}", sources=r.sources) for r in claims[:MAX_ANSWER_CLAIMS]]
    return investor.name, [best_sources(f) for f in facts if f.sources]


def cited(
    sentences: list[Sentence], facts: list[Reason], citations: list[Source]
) -> list[str]:
    """Each sentence followed by its [n] markers (1-based into `citations`, which grows here).
    A sentence that cites no real fact, or states a number its facts don't hold, is dropped."""

    def cite(source: Source) -> int:
        if source not in citations:
            citations.append(source)
        return citations.index(source) + 1

    lines = []
    for sentence in sentences:
        valid = [n for n in dict.fromkeys(sentence.facts) if 1 <= n <= len(facts)]
        used = [facts[n - 1] for n in valid[:MAX_FACTS_PER_SENTENCE]]
        backing = " ".join(f.text for f in used)
        if not used or not set(_NUMBER.findall(sentence.text)) <= set(_NUMBER.findall(backing)):
            continue
        marks = dict.fromkeys(cite(s) for f in used for s in f.sources)
        lines.append((sentence.text.strip() + " " + "".join(f"[{n}]" for n in marks)).strip())
    return lines


def render(draft: _Draft, facts: list[Reason]) -> tuple[str, list[Source]]:
    """Markdown with [n] markers into the returned citations; uncitable sentences dropped."""
    citations: list[Source] = []
    blocks = []
    for section in draft.sections:
        lines = cited(section.sentences, facts, citations)
        if lines:
            blocks.append(f"## {section.heading.strip()}\n\n" + " ".join(lines))
    return "\n\n".join(blocks), citations


async def investor_brief(
    investor_id: str,
    company_id: str,
    competitors: list[Competitor] | None = None,
    space: list[Company] | None = None,
    *,
    graph: Any = None,
) -> Brief:
    """`competitors` / `space` from the founder report's judgement (the API passes its stored
    one); missing = ask the judge.
    `graph` (cache.graph) keeps the brief: the same facts give the same brief again, with no
    Gemini call (20-60 s) and the same wording on every machine. Graph trouble never fails it."""
    store = get_store()
    company = await store.company(company_id)
    if competitors is None or space is None:
        judged = await judge(company)
        competitors = judged.direct if competitors is None else competitors
        space = judged.space if space is None else space
    investor_name, facts = await collect_facts(investor_id, company, competitors, space)
    if not facts:
        raise NotFound(f"no sourced facts about investor {investor_id}")

    numbered = "\n".join(f"{i}. {f.text}" for i, f in enumerate(facts, 1))
    prompt = (
        f"Company (the founder's startup): {company.name}\nInvestor: {investor_name}\n\n"
        f"Facts:\n{numbered}"
    )
    legacy = f"{type(store).__name__}:{investor_id}:{company.id}"  # one doc per pair, older
    told = json.dumps([SYSTEM, prompt, [f.model_dump() for f in facts]])
    fingerprint = hashlib.sha256(told.encode()).hexdigest()
    # One doc per set of facts: a machine that sees other facts (other competitors) adds its
    # brief next to this one instead of replacing it.
    key = f"{legacy}:{fingerprint[:16]}"
    if graph is not None:
        try:
            for doc_id in (key, legacy):
                doc = await graph.get(BRIEFS, doc_id)
                if doc and doc.get("facts") == fingerprint:
                    return Brief.model_validate(doc["brief"])
        except Exception as exc:  # a cache, not a source of truth
            log.warning("brief cache read failed, writing it again: %r", exc)

    draft = await structured(prompt, _Draft, system=SYSTEM, tier="smart")
    markdown, citations = render(draft, facts)
    if not markdown:
        raise LLMError("Gemini wrote no sentence that the facts back; try again")
    brief = Brief(
        investor_id=investor_id, company_id=company.id, markdown=markdown, citations=citations
    )
    if graph is not None:
        try:
            await graph.put(BRIEFS, key, {"facts": fingerprint, "brief": brief.model_dump()})
        except Exception as exc:
            log.warning("brief cache write failed: %r", exc)
    return brief
