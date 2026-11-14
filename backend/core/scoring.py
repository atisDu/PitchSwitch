"""rank_investors (B6): who to pitch, who to skip. Deterministic; no LLM beyond find_competitors.

Split (notes/B.md, agreed 13 Nov):
- Skip  = investors with a PORTFOLIO or BOARD conflict with a *direct* competitor.
- Pitch = investors in rounds of the space (direct competitors + the candidates the judge put in
  the same market space) ∪ co-investors of the company's current investors, minus Skip.
  Unrelated candidates are ignored (they made Stendr's live Pitch list 49 SaaS funds).
- The company's current investors are left out of both lists.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date

from contracts.schemas import (
    Company,
    Competitor,
    Conflict,
    EntityRef,
    FounderReport,
    InvestorScore,
    Reason,
    Round,
)
from core.competitors import judge
from core.conflict import check_conflict, merge_sources
from data import get_store

# Points per signal; they add up to 100. A signal earns its full points at its cap.
# Scoring v2 (B18): companies, not rounds; recency only inside the space; activity counts.
WEIGHTS = {
    "leads_in_space": 30, "companies_in_space": 20, "recency": 15, "activity": 15,
    "warm_paths": 20,
}
CAPS = {"leads_in_space": 2, "companies_in_space": 3, "activity": 6, "warm_paths": 2}
RECENT_MONTHS, STALE_MONTHS = 12, 36  # last lead within 12 mo = full recency, 36+ = none
NO_LEAD_RECENCY = 0.5  # no known lead in the space: the last dated round there counts half
# Cala rarely says who led. In a real round where it names no lead, each of its n investors gets
# 1/n of a lead (the chance it was them) instead of nothing.
BACKERS_ONLY = 0.5  # a company known only from an undated "backers" entry counts half
# ponytail: caps the pool so the real store stays within Cala's rate limit; raise with the cache.
MAX_CO_INVESTORS = 20


def parse_date(text: str | None) -> date | None:
    """'2025-10-03' / '2025-10' / '2025' -> date (missing parts = 1); anything else -> None."""
    parts = (text or "")[:10].split("-")
    try:
        nums = [int(p) for p in parts] + [1, 1]
        return date(nums[0], nums[1], nums[2])
    except (ValueError, IndexError):
        return None


def _recency(when: date | None, today: date) -> float:
    if when is None:
        return 0.0
    months = (today - when).days / 30.44
    if months <= RECENT_MONTHS:
        return 1.0
    return max(0.0, 1 - (months - RECENT_MONTHS) / (STALE_MONTHS - RECENT_MONTHS))


def _capped(signal: str, value: float) -> float:
    return WEIGHTS[signal] * min(value, CAPS[signal]) / CAPS[signal]


def _is_backers(rd: Round) -> bool:
    """A7: Cala's undated list of a company's backers, not a real round."""
    return not rd.label and not rd.date


def _is_lead(rd: Round, investor_id: str) -> bool | None:
    return next((ri.is_lead for ri in rd.investors if ri.investor.id == investor_id), None)


def _points(x: float) -> str:
    return f"{round(x, 1):g}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


async def rank_investors(
    company: Company,
    competitors: list[Competitor] | None = None,
    space: list[Company] | None = None,
    *,
    today: date | None = None,
) -> FounderReport:
    """Rank investors for `company` against direct `competitors` within the market `space`.
    Either one missing = ask the judge (the API passes both, from its memo / competitor_ids)."""
    store = get_store()
    today = today or date.today()
    if competitors is None or space is None:
        judged = await judge(company)
        competitors = judged.direct if competitors is None else competitors
        space = [*(c.company for c in judged.direct), *judged.space] if space is None else space
    direct = {c.company.id for c in competitors}
    others = list({c.id: c for c in space if c.id not in direct and c.id != company.id}.values())
    names = {c.company.id: c.company.name for c in competitors} | {c.id: c.name for c in others}

    space_rounds, own_rounds = await asyncio.gather(
        asyncio.gather(*(store.rounds(i) for i in names)), store.rounds(company.id)
    )
    space: list[Round] = [rd for rds in space_rounds for rd in rds]

    def label(rd: Round) -> str:
        what = f"{names.get(rd.company_id, 'a company')} {rd.label or 'round'}"
        if not rd.label and not rd.date:  # A7: backers with no round details
            return f"{names.get(rd.company_id, 'a company')} (round unknown)"
        return f"{what} ({rd.date})" if rd.date else what

    # The pool: everyone in a space round, plus the top co-investors of current investors.
    pool: dict[str, EntityRef] = {}
    in_space: dict[str, list[Round]] = defaultdict(list)
    for rd in space:
        for ri in rd.investors:
            pool.setdefault(ri.investor.id, ri.investor)
            in_space[ri.investor.id].append(rd)

    current = {ri.investor.id: ri.investor for rd in own_rounds for ri in rd.investors}
    warm: dict[str, list[Reason]] = defaultdict(list)
    shared: dict[str, int] = defaultdict(int)
    co_refs: dict[str, EntityRef] = {}
    co_lists = await asyncio.gather(*(store.co_investors(i) for i in current))
    for cur, co in zip(current.values(), co_lists, strict=True):
        for ref, n in co:
            if ref.id == cur.id:
                continue
            # ponytail: co_investors() has no sources (contract), so warm paths carry none yet.
            warm[ref.id].append(Reason(text=f"Co-invested with your investor {cur.name} ({n}x)"))
            shared[ref.id] += n
            co_refs.setdefault(ref.id, ref)
    # Current investors are already on board: neither a pitch nor a skip.
    for i in [*current, company.id]:
        pool.pop(i, None)
    co_only = sorted(
        (i for i in co_refs if i not in pool and i not in current), key=lambda i: (-shared[i], i)
    )
    for i in co_only[:MAX_CO_INVESTORS]:
        pool[i] = co_refs[i]

    ids = list(pool)
    found = await asyncio.gather(
        asyncio.gather(*(check_conflict(i, competitors, space) for i in ids)),
        asyncio.gather(*(store.investor_rounds(i) for i in ids)),
    )

    pitch: list[InvestorScore] = []
    skip: list[InvestorScore] = []
    for inv_id, conflicts, history in zip(ids, *found, strict=True):
        rounds = in_space[inv_id]
        scored = _score(pool[inv_id], rounds, history, warm[inv_id], conflicts, label, today)
        (skip if conflicts else pitch).append(scored)

    def order(s: InvestorScore):  # ties: the more active, then the wider in the space
        return (-s.score, -(s.deals_last_12m or 0), -s.rounds_in_space, s.investor.name)

    return FounderReport(
        company=company, competitors=competitors, pitch=sorted(pitch, key=order),
        skip=sorted(skip, key=order),
    )


def _score(
    investor: EntityRef,
    rounds: list[Round],
    history: list[Round],
    warm_paths: list[Reason],
    conflicts: list[Conflict],
    label,
    today: date,
) -> InvestorScore:
    inv_id = investor.id
    led = [rd for rd in rounds if _is_lead(rd, inv_id)]
    told = sum(1 for rd in rounds if any(ri.is_lead is not None for ri in rd.investors))
    lead_data = "known" if rounds and told == len(rounds) else "partial" if told else "unknown"

    # Per company in the space: 1 if in a real round, BACKERS_ONLY if only in its backers list;
    # lead credit 1 if it led a round there, else 1/n for a real round that names no lead.
    company: dict[str, float] = {}
    lead: dict[str, float] = {}
    for rd in rounds:
        cid = rd.company_id
        company[cid] = max(company.get(cid, 0.0), BACKERS_ONLY if _is_backers(rd) else 1.0)
        if _is_lead(rd, inv_id):
            credit = 1.0
        elif _is_backers(rd) or any(ri.is_lead is not None for ri in rd.investors):
            credit = 0.0
        else:
            credit = 1 / max(1, len(rd.investors))
        lead[cid] = max(lead.get(cid, 0.0), credit)
    likely = sum(lead.values()) - len({rd.company_id for rd in led})

    every = {rd.id: rd for rd in [*history, *rounds]}.values()
    dated = sorted(
        ((d, rd) for rd in every if (d := parse_date(rd.date))), key=lambda x: x[0], reverse=True
    )
    last_lead = next(((d, rd) for d, rd in dated if _is_lead(rd, inv_id)), None)
    recent = [rd for d, rd in dated if (today - d).days <= 365]
    deals_12m = len(recent) if history else None

    # Recency means "active in your space": only rounds there count.
    space_dated = sorted(
        ((d, rd) for rd in rounds if (d := parse_date(rd.date))), key=lambda x: x[0], reverse=True
    )
    space_lead = next(((d, rd) for d, rd in space_dated if _is_lead(rd, inv_id)), None)
    if space_lead:
        recency, when = _recency(space_lead[0], today), f"last lead here {space_lead[1].date}"
    elif space_dated:
        recency = NO_LEAD_RECENCY * _recency(space_dated[0][0], today)
        when = f"no known lead here; last round here {space_dated[0][1].date}, counted half"
    else:
        recency, when = 0.0, "no dated round here"

    parts = {
        "leads_in_space": _capped("leads_in_space", sum(lead.values())),
        "companies_in_space": _capped("companies_in_space", sum(company.values())),
        "recency": WEIGHTS["recency"] * recency,
        # Like recency: activity only counts for a fund in the space, else busy co-investors with
        # no company here (live: Northzone, Y Combinator on Stendr) outrank those that have one.
        "activity": _capped("activity", deals_12m or 0) if rounds else 0.0,
        "warm_paths": _capped("warm_paths", len(warm_paths)),
    }
    score = sum(parts.values())
    n_led = len({rd.company_id for rd in led})
    details = {
        "leads_in_space": ("leads", f"{n_led} led" + (f", {_points(likely)} likely" if likely
                                                        else "")),
        "companies_in_space": ("companies here", _points(sum(company.values()))),
        "recency": ("recency", when),
        "activity": ("activity", "unknown" if deals_12m is None else f"{deals_12m} in 12 mo"),
        "warm_paths": ("warm paths", str(len(warm_paths))),
    }
    breakdown = " + ".join(
        f"{details[k][0]} {_points(parts[k])}/{WEIGHTS[k]} ({details[k][1]})" for k in WEIGHTS
    )
    # Only with rounds to cite: a co-investor-only score is just its warm paths (listed apart).
    reasons: list[Reason] = [Reason(
        text=f"Score {_points(score)}/100 = {breakdown}",
        sources=merge_sources(*(rd.sources for rd in [*rounds, *recent])),
    )] if rounds else []
    if led:
        reasons.append(Reason(
            text=f"Led {_plural(len(led), 'round')} in this space: {', '.join(map(label, led))}",
            sources=merge_sources(*(rd.sources for rd in led)),
        ))
    joined = [rd for rd in rounds if rd not in led]
    if joined:
        reasons.append(Reason(
            text=f"Took part in {_plural(len(joined), 'round')} in this space: "
            f"{', '.join(map(label, joined))}",
            sources=merge_sources(*(rd.sources for rd in joined)),
        ))
    if last_lead:
        d, rd = last_lead
        reasons.append(Reason(
            text=f"Last led a round on {rd.date}" + (f" ({rd.label})" if rd.label else ""),
            sources=rd.sources,
        ))
    if recent:
        reasons.append(Reason(
            text=f"{_plural(len(recent), 'round')} in the last 12 months",
            sources=merge_sources(*(rd.sources for rd in recent)),
        ))

    return InvestorScore(
        investor=investor,
        score=round(score, 1),
        conflicts=conflicts,
        leads_in_space=len(led),
        rounds_in_space=len(rounds),
        lead_data=lead_data,
        last_lead_date=last_lead[1].date if last_lead else None,
        deals_last_12m=deals_12m,
        warm_paths=warm_paths,
        reasons=reasons,
    )
