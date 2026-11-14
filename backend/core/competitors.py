"""judge / find_competitors (B3): the store's candidates, sorted by Gemini into direct competitors
(Skip side) and same-space companies (their investors are the Pitch pool); the rest is unrelated.

Gemini only picks among candidate IDs and writes a one-line reason; any ID it invents is dropped.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from agent.llm import structured
from cache.graph import default_graph
from contracts.schemas import Company, Competitor, EntityRef
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


VERDICTS = "verdicts"  # graph collection: one doc per (store, company), candidate id -> verdict


def _verdicts_of(judgement: dict, candidates: list[str]) -> dict[str, dict]:
    """A stored judgement as per-candidate verdicts; candidates in neither list are unrelated."""
    out = {i: {"tier": "unrelated"} for i in candidates}
    for n, c in enumerate(judgement["direct"]):
        out[c["company"]["id"]] = {"tier": "direct", "reason": c["reason"], "order": n}
    out |= {c["id"]: {"tier": "space"} for c in judgement["space"]}
    return out


async def _old_verdicts(graph: Any, prefix: str, now: list[str]) -> dict[str, dict]:
    """Verdicts from the judgements stored before VERDICTS (one per candidate list). Where they
    disagree, the one for today's candidate list wins (what the screens show now), then the
    oldest (the plain per-company doc)."""
    ids = [i for i in await graph.ids(JUDGEMENTS) if i == prefix or i.startswith(prefix + ":")]
    docs = [d for i in sorted(ids, key=len) if (d := await graph.get(JUDGEMENTS, i))]
    docs.sort(key=lambda d: d.get("candidates") != now)  # stable: today's list first
    out: dict[str, dict] = {}
    for d in docs:
        for cid, v in _verdicts_of(d["judgement"], d.get("candidates", [])).items():
            out.setdefault(cid, v)
    return out


async def cached_judge(company: Company, graph: Any, k: int = 30) -> Judgement:
    """judge() each candidate once, ever: its verdict (direct / same space / unrelated) is kept in
    `graph` (cache.graph: Atlas when MONGODB_URI is set) and reused whatever list it comes back
    in. Only candidates never judged go to Gemini. Before this, a list that differed by one
    company was judged again from scratch and Gemini could change its mind about the others
    (live: Kelluu's Origin Robotics flipped between same-space and direct, moving its backers
    between Pitch and Skip). Graph trouble never fails the request."""
    store = get_store()
    candidates = await _candidates(company, k)
    doc_id = f"{type(store).__name__}:{company.id}"
    now = sorted(c.id for c in candidates)
    try:
        doc = await graph.get(VERDICTS, doc_id)
        known = doc["verdicts"] if doc else await _old_verdicts(graph, doc_id, now)
    except Exception as exc:  # a cache, not a source of truth
        log.warning("verdicts read failed, judging again: %r", exc)
        known, doc = {}, None
    # A portfolio screen's name-only "unrelated" (B22) is not a verdict on a candidate: judge it.
    new = [c for c in candidates if c.id not in known or known[c.id].get("by") == "name"]
    if new or doc is None:
        if new:
            judged = await judge(company, k, new)
            start = 1 + max((v.get("order", -1) for v in known.values()), default=-1)
            fresh = {c.id: {"tier": "unrelated"} for c in new}
            for n, c in enumerate(judged.direct):
                fresh[c.company.id] = {"tier": "direct", "reason": c.reason, "order": start + n}
            fresh |= {c.id: {"tier": "space"} for c in judged.space}
            known = known | fresh
        known = await _save_verdicts(graph, doc_id, known)
    tier = {c.id: known.get(c.id, {}) for c in candidates}
    direct = sorted(
        (c for c in candidates if tier[c.id].get("tier") == "direct"),
        key=lambda c: tier[c.id].get("order", 0),
    )
    return Judgement(
        direct=[Competitor(company=c, reason=tier[c.id].get("reason", "")) for c in direct][
            :MAX_COMPETITORS
        ],
        space=[c for c in candidates if tier[c.id].get("tier") == "space"],
    )


# --- Portfolio X-ray (B22) ------------------------------------------------------------------
# The judge sees ~30 candidates; an investor's whole portfolio can hide a rival it never saw
# (live: Kelluu's STARTUPLAB backs Hive Autonomy). Portfolio links carry names only, so:
# 1. screen: Gemini reads the names (in batches) and flags likely rivals / same-space companies;
# 2. confirm: only the flagged ones are fetched whole (with descriptions) and go through the
#    regular judge. The verdicts join the same per-startup VERDICTS doc: judged once, ever.

SCREEN = """You screen an investor's portfolio for a startup's founder. Below are company NAMES \
only. Flag in `direct` the IDs of companies that you reliably know sell an overlapping product to \
the same customers as the startup, and in `same_space` those you reliably know work in the same \
market space (adjacent products for the same customers). Leave out companies you do not \
recognise, unrelated companies, investors and funds: when unsure, leave it out (the flagged ones \
are checked again with their descriptions). Use only IDs from the list, copied exactly."""
SCREEN_BATCH = 120  # names per screening call
MAX_CONFIRM = 60  # flagged companies fetched and judged per startup and call; the rest wait


class _Screen(BaseModel):
    direct: list[str]
    same_space: list[str]


_verdict_memo: dict[str, dict[str, dict]] = {}  # VERDICTS doc id -> verdicts, this process


def _doc_id(company: Company) -> str:
    return f"{type(get_store()).__name__}:{company.id}"


async def _load_verdicts(graph: Any, doc_id: str) -> dict[str, dict]:
    if doc_id not in _verdict_memo:
        doc = await graph.get(VERDICTS, doc_id)
        _verdict_memo[doc_id] = dict(doc["verdicts"]) if doc else {}
    return _verdict_memo[doc_id]


async def _save_verdicts(graph: Any, doc_id: str, verdicts: dict[str, dict]) -> dict[str, dict]:
    """Merge into the stored doc; a verdict already stored wins (verdicts are sticky, and another
    process may have written since we read). Returns the merged verdicts. Never raises."""
    merged = dict(verdicts)
    try:
        doc = await graph.get(VERDICTS, doc_id)
        for i, stored in ((doc or {}).get("verdicts") or {}).items():
            if not (stored.get("by") == "name" and merged.get(i, {}).get("by", "") != "name"):
                merged[i] = stored  # except a name-only screen, which a full verdict replaces
        await graph.put(VERDICTS, doc_id, {"verdicts": merged})
    except Exception as exc:  # a cache, not a source of truth
        log.warning("verdicts write failed: %r", exc)
    _verdict_memo[doc_id] = merged
    return merged


def _name_line(ref: EntityRef) -> str:
    return f"- id={ref.id} | {ref.name}"


async def portfolio_verdicts(
    company: Company, refs: list[EntityRef], graph: Any = None
) -> dict[str, dict]:
    """Company id -> verdict ({"tier": "direct" | "space" | "unrelated", "reason"?}) for these
    portfolio companies, judged against `company`. Never-judged ones are screened and confirmed
    (see above) and stored. A company that could not be judged this time (Gemini or Cala
    trouble) is missing from the result and tried again next time. Never raises."""
    graph = graph or shared_graph()
    doc_id = _doc_id(company)
    try:
        known = await _load_verdicts(graph, doc_id)
    except Exception as exc:
        log.warning("verdicts read failed, X-ray skipped: %r", exc)
        return {}
    todo = {r.id: r for r in refs if r.id not in known and r.id != company.id}
    if todo:
        fresh = await _xray_judge(company, list(todo.values()), known)
        if fresh:
            known = await _save_verdicts(graph, doc_id, known | fresh)
    return {r.id: known[r.id] for r in refs if r.id in known}


async def _xray_judge(
    company: Company, refs: list[EntityRef], known: dict[str, dict]
) -> dict[str, dict]:
    batches = [refs[i : i + SCREEN_BATCH] for i in range(0, len(refs), SCREEN_BATCH)]
    head = f"Startup:\n{_line(company)}\n\nPortfolio companies:\n"
    screened = await asyncio.gather(
        *(
            structured(head + "\n".join(map(_name_line, b)), _Screen, system=SCREEN, tier="fast")
            for b in batches
        ),
        return_exceptions=True,
    )
    fresh: dict[str, dict] = {}
    flagged: list[str] = []
    for batch, got in zip(batches, screened, strict=True):
        if isinstance(got, BaseException):
            log.warning("portfolio screen failed for %d companies: %r", len(batch), got)
            continue  # not stored: screened again next time
        ids = {r.id for r in batch}
        hits = [i.strip() for i in [*got.direct, *got.same_space] if i.strip() in ids]
        flagged += [i for i in dict.fromkeys(hits) if i not in flagged]
        fresh |= {i: {"tier": "unrelated", "by": "name"} for i in ids if i not in hits}
    suspects = flagged[:MAX_CONFIRM]
    if not suspects:
        return fresh
    found = await asyncio.gather(
        *(get_store().company(i) for i in suspects), return_exceptions=True
    )
    whole = [c for c in found if isinstance(c, Company)]
    if not whole:
        return fresh
    try:
        judged = await judge(company, candidates=whole)
    except Exception as exc:
        log.warning("portfolio confirm failed for %d companies: %r", len(whole), exc)
        return fresh
    start = 1 + max((v.get("order", -1) for v in known.values()), default=-1)
    fresh |= {c.id: {"tier": "unrelated", "by": "portfolio"} for c in whole}
    for n, c in enumerate(judged.direct):
        fresh[c.company.id] = {
            "tier": "direct", "reason": c.reason, "order": start + n, "by": "portfolio"
        }
    fresh |= {c.id: {"tier": "space", "by": "portfolio"} for c in judged.space}
    return fresh


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
