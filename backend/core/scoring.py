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
import re
from collections import defaultdict
from datetime import date

from cache.vector import COLLECTION as VECTORS
from cache.vector import cosine
from contracts.schemas import (
    Company,
    Competitor,
    Conflict,
    EntityRef,
    FounderReport,
    InvestorScore,
    PortfolioLink,
    Reason,
    Round,
)
from core.competitors import judge, shared_graph
from core.conflict import check_conflict, merge_sources
from core.fresh import (
    TOP_PARTNERS,
    board_conflicts,
    fresh_funds,
    lead_partner,
    partner_reason,
    sector_of,
)
from core.funding import raise_fit
from core.notes import report_notes
from core.sanctions import screen_all
from core.xray import XRay, hidden_reasons, portfolios_of, thesis_reason
from core.xray import xray as portfolio_xray
from data import get_store
from data.mappers import STAGES, country_of, name_key, stage_index

# Points per signal; they add up to 100. A signal earns its full points at its cap.
# Scoring v2 (B18): companies, not rounds; recency only inside the space; activity counts.
# B19: closeness weights each company; stage fit and geography. Unknown data earns 0 and says so.
WEIGHTS = {
    "leads_in_space": 25, "companies_in_space": 15, "recency": 15, "activity": 10,
    "warm_paths": 15, "stage_fit": 10, "geography": 10,
}
FRESH_COMPANIES = 0.5  # B26: share of the companies-here points a fresh sector fund earns
CAPS = {"leads_in_space": 2, "companies_in_space": 3, "activity": 6, "warm_paths": 2}
# Closeness: a company in the space counts 0.75-1.25 by how similar it is to the startup (cosine
# of the stored vectors, relative to the rest of the space; live they all sit in 0.79-0.89, so
# this is a nudge), a direct competitor 1.25, a company without a vector 1.
CLOSE_MIN, CLOSE_MAX, CLOSE_DIRECT = 0.75, 1.25, 1.25
NORDIC_BALTIC = {
    "finland", "sweden", "norway", "denmark", "iceland", "estonia", "latvia", "lithuania",
}
# Cala often has no country for a fund (live: Maki.vc) while its description says "Helsinki-based".
_NORDIC_WORDS = re.compile(
    r"\b(" + "|".join([
        *NORDIC_BALTIC, "nordic", "nordics", "baltic", "baltics", "finnish", "swedish",
        "norwegian", "danish", "icelandic", "estonian", "latvian", "lithuanian", "helsinki",
        "espoo", "tampere", "turku", "oulu", "stockholm", "gothenburg", "malmö", "oslo",
        "bergen", "trondheim", "copenhagen", "aarhus", "reykjavik", "tallinn", "tartu", "riga",
        "vilnius", "kaunas",
    ]) + r")\b",
    re.IGNORECASE,
)
RECENT_MONTHS, STALE_MONTHS = 12, 36  # last lead within 12 mo = full recency, 36+ = none
NO_LEAD_RECENCY = 0.5  # no known lead in the space: the last dated round there counts half
# Cala rarely says who led. In a real round where it names no lead, each of its n investors gets
# 1/n of a lead (the chance it was them) instead of nothing.
BACKERS_ONLY = 0.5  # a company known only from an undated "backers" entry counts half
# B22: a same-space company found only in the investor's portfolio (no round of it in the space
# lists the investor) counts half, like a backers entry: Cala names the link, not the deal.
PORTFOLIO_ONLY = 0.5
# ponytail: caps the pool so the real store stays within Cala's rate limit; raise with the cache.
MAX_CO_INVESTORS = 20
# B20: no known investor of the startup (live: Sensofusion) -> the funds that led a round in the
# space stand in for them; a path through one counts half.
WARM_FALLBACK = 0.5
MAX_WARM_SOURCES = 6


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


async def _closeness(company: Company, direct: set[str], others: list[Company]) -> dict[str, float]:
    """Company id -> weight (see CLOSE_*). {} when vectors are unavailable (fake store, vector
    search off, graph trouble): every company then counts 1."""
    try:
        graph = shared_graph()
        ids = [company.id, *(c.id for c in others)]
        docs = await asyncio.gather(*(graph.get(VECTORS, i) for i in ids))
    except Exception:  # a nudge, never a reason to fail the report
        return dict.fromkeys(direct, CLOSE_DIRECT)
    vec = {i: d["embedding"] for i, d in zip(ids, docs, strict=True) if d and d.get("embedding")}
    me = vec.get(company.id)
    sims = {i: cosine(me, v) for i, v in vec.items() if me and i != company.id}
    out = dict.fromkeys(direct, CLOSE_DIRECT)
    if len(sims) >= 2:
        lo, hi = min(sims.values()), max(sims.values())
        for i, sim in sims.items():
            if i not in direct:
                out[i] = CLOSE_MIN + (CLOSE_MAX - CLOSE_MIN) * (sim - lo) / ((hi - lo) or 1)
    return out


def _startup_stage(company: Company, own_rounds: list[Round]) -> int | None:
    """The startup's stage on the STAGES ladder; Cala's funding_stage, else its latest round."""
    if (at := stage_index(company.stage)) is not None:
        return at
    labelled = [rd for rd in own_rounds if stage_index(rd.label) is not None]
    latest = max(labelled, key=lambda rd: rd.date or "", default=None)
    return stage_index(latest.label) if latest else None


async def _warm_paths(
    anchors: dict[str, EntityRef], histories: dict[str, list[Round]], *, mine: bool
) -> dict[str, list[Reason]]:
    """Investor id -> one Reason per anchor it has backed a company with, most companies first.
    Evidence: a round both took part in, or a company in both portfolios; the sources are those
    rounds' and links'. A pair with no such evidence gets no path (it could not be cited).
    `mine`: the anchors are the startup's own investors, else funds that lead in its space."""
    store = get_store()
    a_ids = list(anchors)
    missing = [a for a in a_ids if a not in histories]
    got = await asyncio.gather(
        asyncio.gather(*(store.investor_rounds(a) for a in missing)),
        asyncio.gather(*(store.portfolio(i) for i in [*a_ids, *histories])),
    )
    rounds_of = histories | dict(zip(missing, got[0], strict=True))
    links = dict(zip([*a_ids, *histories], got[1], strict=True))
    by_company = {i: {lk.company.id: lk for lk in ls} for i, ls in links.items()}
    out: dict[str, list[Reason]] = defaultdict(list)
    for inv in histories:
        found: list[tuple[int, Reason]] = []
        for a in a_ids:
            if a == inv:
                continue
            both = {
                rd.id: rd
                for rd in [*rounds_of.get(a, []), *rounds_of.get(inv, [])]
                if {a, inv} <= {ri.investor.id for ri in rd.investors}
            }
            mine_c, theirs = by_company.get(a, {}), by_company.get(inv, {})
            common = mine_c.keys() & theirs.keys()
            companies = {rd.company_id for rd in both.values()} | common
            if not companies:
                continue
            names = sorted({mine_c[c].company.name for c in common})[:2]
            who = f"your investor {anchors[a].name}" if mine else (
                f"{anchors[a].name}, which led a round in your space")
            n = len(companies)
            text = f"Co-invested in {_plural(n, 'compan')} with {who}" + (
                f" (e.g. {', '.join(names)})" if names else "")
            sources = merge_sources(
                *(rd.sources for rd in both.values()),
                *(mine_c[c].sources + theirs[c].sources for c in sorted(common)),
            )[:MAX_WARM_SOURCES]
            found.append((n, Reason(text=text, sources=sources)))
        out[inv] = [r for _, r in sorted(found, key=lambda x: -x[0])]
    return out


def _is_backers(rd: Round) -> bool:
    """A7: Cala's undated list of a company's backers, not a real round."""
    return not rd.label and not rd.date


def _is_lead(rd: Round, investor_id: str) -> bool | None:
    return next((ri.is_lead for ri in rd.investors if ri.investor.id == investor_id), None)


def _points(x: float) -> str:
    return f"{round(x, 1):g}"


def _plural(n: int, word: str) -> str:
    if word.endswith("compan"):  # company / companies
        return f"{n} {word}{'y' if n == 1 else 'ies'}"
    return f"{n} {word}{'' if n == 1 else 's'}"


async def rank_investors(
    company: Company,
    competitors: list[Competitor] | None = None,
    space: list[Company] | None = None,
    *,
    today: date | None = None,
    target_amount_eur: float | None = None,
    xray: bool = False,
    this_week: bool = False,
    screen: bool = False,
    notes: bool = False,
) -> FounderReport:
    """Rank investors for `company` against direct `competitors` within the market `space`.
    Either one missing = ask the judge (the API passes both, from its memo / competitor_ids).
    `xray` (B22): also judge every ranked investor's whole portfolio (Gemini, stored once per
    startup): hidden rivals there move it to Skip, same-space companies count as its thesis.
    `this_week` (B23): funds that just closed for the sector join the pool, and the top Pitch
    investors get their lead partner, who is checked against the direct competitors' boards.
    `screen` (B25): every ranked investor and its LPs against Cala's sanctions records; a record
    is a SANCTION conflict (Skip), none gives "screened: no sanctions record in Cala".
    `notes` (B24): sourced lines on the direct competitors (grants won, at Slush 2026)."""
    store = get_store()
    today = today or date.today()
    if competitors is None or space is None:
        judged = await judge(company)
        competitors = judged.direct if competitors is None else competitors
        space = [*(c.company for c in judged.direct), *judged.space] if space is None else space
    sector = sector_of(company, [*(c.company for c in competitors), *space])
    # Cala's search for fresh funds is slow when not stored: start it now.
    funds_task = asyncio.create_task(fresh_funds(sector, today)) if this_week else None
    notes_task = asyncio.create_task(report_notes(company, competitors)) if notes else None
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
    # co_investors() (A's precomputed graph) only picks who else to rank: it has no sources.
    # The warm paths themselves are rebuilt from sourced rounds and portfolios (_warm_paths).
    shared: dict[str, int] = defaultdict(int)
    co_refs: dict[str, EntityRef] = {}
    co_lists = await asyncio.gather(*(store.co_investors(i) for i in current))
    for cur, co in zip(current.values(), co_lists, strict=True):
        for ref, n in co:
            if ref.id != cur.id:
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
    fresh: dict[str, Reason] = {}
    for ref, why in await funds_task if funds_task else []:
        if ref.id not in current and ref.id != company.id:
            pool.setdefault(ref.id, ref)
            fresh[ref.id] = why

    ids = list(pool)
    portfolios: dict[str, list[PortfolioLink]] = await portfolios_of(ids) if xray else {}
    # Never "hidden": the judge's direct competitors (also ones the user removed) and the space.
    listed = {company.id, *names, *(c.company.id for c in competitors)}
    xrays = await portfolio_xray(company, portfolios, listed) if xray else {}
    found = await asyncio.gather(
        asyncio.gather(
            *(
                check_conflict(
                    i,
                    competitors,
                    space,
                    hidden=xrays[i].hidden if i in xrays else [],
                    portfolio=portfolios.get(i),
                )
                for i in ids
            )
        ),
        asyncio.gather(*(store.investor_rounds(i) for i in ids)),
        asyncio.gather(*(store.company(i) for i in ids), return_exceptions=True),
    )
    screens = await screen_all([pool[i] for i in ids]) if screen else {}
    close = await _closeness(company, direct, others)
    stage = _startup_stage(company, own_rounds)
    leaders = {ri.investor.id: ri.investor for rd in space for ri in rd.investors if ri.is_lead}
    anchors = current or {i: ref for i, ref in leaders.items() if i != company.id}
    warm = await _warm_paths(anchors, dict(zip(ids, found[1], strict=True)), mine=bool(current))
    warm_weight = 1.0 if current else WARM_FALLBACK

    pitch: list[InvestorScore] = []
    skip: list[InvestorScore] = []
    for inv_id, conflicts, history, profile in zip(ids, *found, strict=True):
        screened = screens.get(inv_id)
        if screened:
            conflicts = [*conflicts, *screened.conflicts]
        scored = _score(
            pool[inv_id], in_space[inv_id], history, warm[inv_id], conflicts, label, today,
            closeness=close, stage=stage, warm_weight=warm_weight,
            profile=profile if isinstance(profile, Company) else None,
            xray=xrays.get(inv_id), fresh=fresh.get(inv_id),
        )
        if screened:
            scored.reasons.extend(screened.reasons)
        if target_amount_eur:
            scored.funding_fit = raise_fit(target_amount_eur, history, pool[inv_id].name)
        (skip if conflicts else pitch).append(scored)
    everyone = _one_per_firm([*pitch, *skip])
    pitch = [s for s in everyone if not s.conflicts]
    skip = [s for s in everyone if s.conflicts]

    def order(s: InvestorScore):  # ties: the more active, then the wider in the space
        return (-s.score, -(s.deals_last_12m or 0), -s.rounds_in_space, s.investor.name)

    if this_week:  # B23 (b): the partner of each top Pitch investor
        top = [s for s in sorted(pitch, key=order) if s.investor.type != "Person"][:TOP_PARTNERS]
        def deals(inv_id: str) -> list[str]:  # its companies in the space, rounds first
            held = [names.get(rd.company_id) for rd in in_space[inv_id]]
            held += [lk.company.name for lk in (xrays[inv_id].thesis if inv_id in xrays else [])]
            return list(dict.fromkeys(n for n in held if n))

        partners = await asyncio.gather(
            *(lead_partner(s.investor, sector, deals=deals(s.investor.id)) for s in top)
        )
        for s, partner in zip(top, partners, strict=True):
            if not partner:
                continue
            s.reasons.append(partner_reason(partner))
            board = await board_conflicts(partner, competitors)
            if board:
                s.conflicts = [*s.conflicts, *board]
                s.reasons.extend(
                    Reason(
                        text=f"Conflict: its partner {partner['name']} sits on the board of "
                        f"{c.competitor.name}, a direct competitor",
                        sources=c.sources,
                    )
                    for c in board
                )
                pitch.remove(s)
                skip.append(s)

    return FounderReport(
        company=company, competitors=competitors, pitch=sorted(pitch, key=order),
        skip=sorted(skip, key=order), notes=await notes_task if notes_task else [],
    )


def _same_firm(a: EntityRef, b: EntityRef) -> bool:
    """Two Cala entries of one fund (live: Maki.vc 415bc278 and 8f0ff46d): same name without the
    legal form, no sign of different countries; never people (two angels can share a name)."""
    if "Person" in (a.type, b.type) or not name_key(a.name) or name_key(a.name) != name_key(b.name):
        return False
    here, there = country_of(None, a.description), country_of(None, b.description)
    return here is None or there is None or here == there


def _one_per_firm(scores: list[InvestorScore]) -> list[InvestorScore]:
    """One card per firm: the best-scored entry stays; the conflicts of every entry are kept on
    it (a conflict on either entry still means Skip), with their 'Conflict: ...' reasons."""
    kept: list[InvestorScore] = []
    for s in sorted(scores, key=lambda s: -s.score):
        main = next((k for k in kept if _same_firm(k.investor, s.investor)), None)
        if main is None:
            kept.append(s)
            continue
        main.conflicts += [c for c in s.conflicts if c not in main.conflicts]
        main.reasons += [
            r for r in s.reasons if r.text.startswith("Conflict") and r not in main.reasons
        ]
    return kept


def _score(
    investor: EntityRef,
    rounds: list[Round],
    history: list[Round],
    warm_paths: list[Reason],
    conflicts: list[Conflict],
    label,
    today: date,
    *,
    closeness: dict[str, float] | None = None,
    stage: int | None = None,
    profile: Company | None = None,
    warm_weight: float = 1.0,
    xray: XRay | None = None,
    fresh: Reason | None = None,
) -> InvestorScore:
    inv_id = investor.id
    led = [rd for rd in rounds if _is_lead(rd, inv_id)]
    told = sum(1 for rd in rounds if any(ri.is_lead is not None for ri in rd.investors))
    lead_data = "known" if rounds and told == len(rounds) else "partial" if told else "unknown"

    # Per company in the space: 1 if in a real round, BACKERS_ONLY if only in its backers list;
    # lead credit 1 if it led a round there, else 1/n for a real round that names no lead.
    company: dict[str, float] = {}
    lead: dict[str, float] = {}
    weight = closeness or {}
    for rd in rounds:
        cid = rd.company_id
        w = weight.get(cid, 1.0)
        company[cid] = max(company.get(cid, 0.0), (BACKERS_ONLY if _is_backers(rd) else 1.0) * w)
        if _is_lead(rd, inv_id):
            credit = 1.0
        elif _is_backers(rd) or any(ri.is_lead is not None for ri in rd.investors):
            credit = 0.0
        else:
            credit = 1 / max(1, len(rd.investors))
        lead[cid] = max(lead.get(cid, 0.0), credit * w)
    # B22: same-space companies only in its portfolio count half (PORTFOLIO_ONLY).
    thesis = xray.thesis if xray else []
    portfolio_only = [lk for lk in thesis if lk.company.id not in company]
    for lk in portfolio_only:
        company[lk.company.id] = PORTFOLIO_ONLY * weight.get(lk.company.id, 1.0)
    # In the space: by a deal, by its portfolio (B22) or by a fund just closed for it (B23).
    here = bool(rounds or portfolio_only or fresh)
    led_ids = {rd.company_id for rd in led}
    likely = sum(v for cid, v in lead.items() if cid not in led_ids)

    # Stage fit: share of the investor's labelled rounds at the startup's stage or the next one.
    staged = [(rd, at) for rd in history if (at := stage_index(rd.label)) is not None]
    at_stage = [rd for rd, at in staged if stage is not None and at in (stage, stage + 1)]
    stage_share = len(at_stage) / len(staged) if staged and stage is not None else None
    country = (profile.country or "").strip() if profile else ""
    nordic = country.lower() in NORDIC_BALTIC
    if profile and not country and (said := _NORDIC_WORDS.search(profile.description or "")):
        country, nordic = f"{said.group()}, from its description", True

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
        # B26: a fund just closed for the sector is a thesis on it: at least half the points.
        "companies_in_space": max(
            _capped("companies_in_space", sum(company.values())),
            WEIGHTS["companies_in_space"] * FRESH_COMPANIES if fresh else 0.0,
        ),
        "recency": WEIGHTS["recency"] * recency,
        # Like recency: activity only counts for a fund in the space, else busy co-investors with
        # no company here (live: Northzone, Y Combinator on Stendr) outrank those that have one.
        # B23: a fund just closed for the sector is activity now: full points.
        "activity": WEIGHTS["activity"] if fresh else (
            _capped("activity", deals_12m or 0) if here else 0.0),
        "warm_paths": _capped("warm_paths", len(warm_paths) * warm_weight),
        # Like activity: only for an investor with a company in the space.
        "stage_fit": WEIGHTS["stage_fit"] * (stage_share or 0.0) if here else 0.0,
        "geography": WEIGHTS["geography"] if nordic and here else 0.0,
    }
    score = sum(parts.values())
    n_led = len({rd.company_id for rd in led})
    details = {
        "leads_in_space": ("leads", f"{n_led} led" + (f", {_points(likely)} likely" if likely
                                                        else "")),
        "companies_in_space": (
            "companies here",
            f"{_plural(len(company), 'compan')}, "
            f"{_points(sum(company.values()))} weighted by closeness"
            if weight and any(cid in weight for cid in company)
            else _points(sum(company.values())),
        ) if not portfolio_only else (
            "companies here",
            f"{_plural(len(company), 'compan')}, {len(portfolio_only)} of them only in its "
            f"portfolio, counted half; {_points(sum(company.values()))} in all",
        ),
        "recency": ("recency", when),
        "activity": ("activity", ("fresh fund for your sector" + (
            f", {deals_12m} in 12 mo" if deals_12m else "")) if fresh else
            "unknown" if deals_12m is None else f"{deals_12m} in 12 mo"),
        "warm_paths": ("warm paths", str(len(warm_paths)) + (
            ", through funds that lead here, counted half" if warm_paths and warm_weight < 1
            else "")),
        "stage_fit": ("stage fit", "startup stage unknown" if stage is None else
                      "no labelled rounds" if not staged else
                      f"{len(at_stage)} of {len(staged)} rounds at {STAGES[stage]}"
                      + (f"-{STAGES[stage + 1]}" if stage + 1 < len(STAGES) else "")),
        "geography": ("Nordic/Baltic", country or "country unknown"),
    }
    if fresh and parts["companies_in_space"] > _capped("companies_in_space", sum(company.values())):
        details["companies_in_space"] = (
            "companies here", "fresh fund for your sector, counted half"
        )
    breakdown = " + ".join(
        f"{details[k][0]} {_points(parts[k])}/{WEIGHTS[k]} ({details[k][1]})" for k in WEIGHTS
    )
    # Only with rounds to cite: a co-investor-only score is just its warm paths (listed apart).
    reasons: list[Reason] = [Reason(
        text=f"Score {_points(score)}/100 = {breakdown}",
        sources=merge_sources(
            *(rd.sources for rd in [*rounds, *recent, *at_stage]),
            *(lk.sources for lk in portfolio_only),
            fresh.sources if fresh else [],
            profile.sources if profile and nordic else [],
        ),
    )] if here else []
    if xray:
        reasons += hidden_reasons(xray, {c.competitor.id for c in conflicts})
    if fresh:
        reasons.append(fresh)
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
    if xray and (held := thesis_reason(xray)):
        reasons.append(held)
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
