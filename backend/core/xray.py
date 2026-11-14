"""Portfolio X-ray (B22): what an investor's whole portfolio says about a startup.

The competitor judge only sees ~30 candidates. Here every company in an investor's portfolio is
judged against the startup too (`core.competitors.portfolio_verdicts`: screened by name,
confirmed with descriptions, stored once per startup). Two uses:

- a direct rival that is not on the startup's competitor list = a hidden PORTFOLIO conflict
  (`check_conflict(..., hidden=...)`), so the investor goes to Skip;
- same-space companies = the investor's thesis: they count towards "companies here" in the
  score and are listed in a reason.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from contracts.schemas import Company, Competitor, PortfolioLink, Reason
from core.competitors import portfolio_verdicts
from core.conflict import merge_sources
from data import get_store

HIDDEN = "not on your competitor list"
MAX_NAMED = 4  # companies named in the thesis reason
MAX_SOURCES = 6


@dataclass
class XRay:
    hidden: list[Competitor] = field(default_factory=list)  # direct rivals off the list
    thesis: list[PortfolioLink] = field(default_factory=list)  # same-space portfolio companies


async def xray(
    company: Company, portfolios: dict[str, list[PortfolioLink]], listed: set[str]
) -> dict[str, XRay]:
    """Investor id -> its X-ray. `listed`: company ids already on the report (the judge's direct
    competitors, also ones the user removed, and the market space): never "hidden"."""
    refs = {lk.company.id: lk.company for links in portfolios.values() for lk in links}
    tiers = await portfolio_verdicts(company, list(refs.values()))
    out: dict[str, XRay] = {}
    for inv, links in portfolios.items():
        x = XRay()
        for lk in {lk.company.id: lk for lk in links}.values():
            cid = lk.company.id
            tier = tiers.get(cid, {}).get("tier")
            if cid == company.id or tier is None:
                continue
            if tier == "direct" and cid not in listed:
                rival = Company(**lk.company.model_dump(), sources=lk.sources)
                why = tiers[cid].get("reason") or "Judged a direct rival."
                x.hidden.append(Competitor(company=rival, reason=f"{why} ({HIDDEN})"))
            elif tier == "space":
                x.thesis.append(lk)
        out[inv] = x
    return out


async def hidden_rivals(
    company: Company, investor_id: str, competitors: list[Competitor], space: list[Company]
) -> list[Competitor]:
    """One investor's hidden rivals (investor check, briefs, agent and MCP tools), against the
    judge's `competitors` and market `space` for `company`."""
    listed = {company.id, *(c.company.id for c in competitors), *(c.id for c in space)}
    links = await get_store().portfolio(investor_id)
    return (await xray(company, {investor_id: links}, listed))[investor_id].hidden


def hidden_reasons(x: XRay, conflicts_with: set[str]) -> list[Reason]:
    """One reason per hidden rival the investor is skipped for."""
    return [
        Reason(
            text=f"Hidden conflict: backs {c.company.name}, a direct rival {HIDDEN} "
            f"({c.reason.removesuffix(f' ({HIDDEN})')})",
            sources=c.company.sources,
        )
        for c in x.hidden
        if c.company.id in conflicts_with
    ]


def thesis_reason(x: XRay) -> Reason | None:
    if not x.thesis:
        return None
    names = sorted(lk.company.name for lk in x.thesis)
    shown = ", ".join(names[:MAX_NAMED]) + (", …" if len(names) > MAX_NAMED else "")
    n = len(names)
    return Reason(
        text=f"Its portfolio holds {n} {'company' if n == 1 else 'companies'} in your space: "
        f"{shown}",
        sources=merge_sources(*(lk.sources for lk in x.thesis))[:MAX_SOURCES],
    )


async def portfolios_of(ids: list[str]) -> dict[str, list[PortfolioLink]]:
    store = get_store()
    got = await asyncio.gather(*(store.portfolio(i) for i in ids))
    return dict(zip(ids, got, strict=True))
