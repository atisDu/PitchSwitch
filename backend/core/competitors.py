"""judge / find_competitors (B3): the store's candidates, sorted by Gemini into direct competitors
(Skip side) and same-space companies (their investors are the Pitch pool); the rest is unrelated.

Gemini only picks among candidate IDs and writes a one-line reason; any ID it invents is dropped.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from pydantic import BaseModel

from agent.llm import structured
from cache.graph import default_graph
from contracts.schemas import Company, Competitor
from data import get_store

MAX_COMPETITORS = 15
JUDGEMENTS = "judgements"  # graph collection: one judgement per (store, company)

log = logging.getLogger("core.competitors")

SYSTEM = """You judge which companies are DIRECT competitors of a startup, for a founder deciding \
which investors to pitch (an investor who backed a direct competitor has a conflict).
A direct competitor sells an overlapping product to the same customers (e.g. both build \
counter-drone systems, or both sell aerial surveillance). Sharing a broad industry such as \
"aerospace and defense" is not enough. Investors, funds, agencies and suppliers are never \
competitors.
The descriptions come from a database and are often thin: combine them with what you reliably \
know about these named companies. Do not guess about companies you do not know.
Return the direct competitors, most direct first, at most 15; return none if none qualify. Use \
only IDs from the candidate list, copied exactly. Each reason is one short sentence naming the \
overlap; no numbers, dates, funding or investor names.
Separately, list in same_space the IDs of the other candidates that work in the same market \
space without being direct competitors (adjacent products for the same customers, e.g. other \
drone or defence hardware for a counter-drone startup): investors who back them are likely to \
back the startup. Leave unrelated companies out of both lists."""


class _Pick(BaseModel):
    id: str
    reason: str


class _Judgement(BaseModel):
    competitors: list[_Pick]
    same_space: list[str]


class Judgement(BaseModel):
    direct: list[Competitor]  # Skip side: backing one of these is a conflict
    space: list[Company]  # same market, not direct: their backers form the Pitch pool


def _line(c: Company) -> str:
    facts = [
        f"industries: {', '.join(c.industries)}" if c.industries else "",
        f"stage: {c.stage}" if c.stage else "",
        f"country: {c.country}" if c.country else "",
    ]
    meta = "; ".join(f for f in facts if f)
    return f"- id={c.id} | {c.name} | {c.description or 'no description'}" + (
        f" | {meta}" if meta else ""
    )


async def _candidates(company: Company, k: int) -> list[Company]:
    return [c for c in await get_store().candidate_competitors(company, k) if c.id != company.id]


async def judge(
    company: Company, k: int = 30, candidates: list[Company] | None = None
) -> Judgement:
    if candidates is None:
        candidates = await _candidates(company, k)
    if not candidates:
        return Judgement(direct=[], space=[])
    by_id = {c.id: c for c in candidates}
    prompt = (
        f"Startup:\n{_line(company)}\n\n"
        f"Candidates:\n" + "\n".join(_line(c) for c in by_id.values())
    )
    judged = await structured(prompt, _Judgement, system=SYSTEM, tier="smart")

    direct: list[Competitor] = []
    for pick in judged.competitors:
        c = by_id.pop(pick.id.strip(), None)  # pop: unknown and repeated IDs are both dropped
        if c is not None:
            direct.append(Competitor(company=c, reason=pick.reason.strip()))
    space = [c for i in judged.same_space if (c := by_id.pop(i.strip(), None))]
    return Judgement(direct=direct[:MAX_COMPETITORS], space=space)


async def find_competitors(company: Company, k: int = 30) -> list[Competitor]:
    return (await judge(company, k)).direct


async def cached_judge(company: Company, graph: Any, k: int = 30) -> Judgement:
    """judge() once per company and candidate list, kept in `graph` (cache.graph: Atlas when
    MONGODB_URI is set). Same report across restarts and machines, and no 20-25 s Gemini call.
    Each candidate list has its own stored judgement, so two machines that see different
    candidates for one company (vector search on / off) never overwrite each other, and a list
    that comes back gets its earlier judgement back. Graph trouble never fails the request."""
    store = get_store()
    candidates = await _candidates(company, k)
    legacy = f"{type(store).__name__}:{company.id}"  # one doc per company, written before this
    fingerprint = sorted(c.id for c in candidates)
    key = f"{legacy}:{hashlib.sha256(' '.join(fingerprint).encode()).hexdigest()[:16]}"
    try:
        for doc_id in (key, legacy):
            doc = await graph.get(JUDGEMENTS, doc_id)
            if doc and doc.get("candidates") == fingerprint:
                return Judgement.model_validate(doc["judgement"])
    except Exception as exc:  # a cache, not a source of truth
        log.warning("judgement cache read failed, judging again: %r", exc)
    judged = await judge(company, k, candidates)
    try:
        document = {"candidates": fingerprint, "judgement": judged.model_dump(mode="json")}
        await graph.put(JUDGEMENTS, key, document)
    except Exception as exc:
        log.warning("judgement cache write failed: %r", exc)
    return judged


# One judgement per company for the whole process: the API routes, the agent tools and the MCP
# tools all read it here, so "direct competitor" means the same everywhere. The dict is a shortcut
# in front of the graph store. ponytail: unbounded; fine for a demo-sized set.
_memo: dict[str, Judgement] = {}
_graph: Any = None


def shared_graph() -> Any:
    """The graph store of this process (Atlas when MONGODB_URI is set)."""
    global _graph
    _graph = _graph or default_graph()
    return _graph


async def stored_judgement(company: Company) -> Judgement:
    if company.id not in _memo:
        _memo[company.id] = await cached_judge(company, shared_graph())
    return _memo[company.id]
