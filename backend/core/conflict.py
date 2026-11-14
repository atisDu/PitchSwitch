"""check_conflict (B4 PORTFOLIO, B5 BOARD): does an investor have a stake in a direct competitor?

Plain set logic over store data; every Conflict carries the sources of the edges it rests on.
The founder report, the investor check, briefs, chat and the MCP tools all decide here.
"""

from __future__ import annotations

import asyncio

from contracts.schemas import Competitor, Conflict, EntityRef, PortfolioLink, Round, Source
from data import get_store


def ref_of(c: Competitor) -> EntityRef:
    co = c.company
    return EntityRef(id=co.id, name=co.name, type=co.type, description=co.description)


def merge_sources(*lists: list[Source]) -> list[Source]:
    out: list[Source] = []
    for sources in lists:
        out += [s for s in sources if s not in out]
    return out


async def check_conflict(
    investor_id: str,
    competitors: list[Competitor],
    rounds: list[Round] | None = None,
    *,
    hidden: list[Competitor] = (),
    portfolio: list[PortfolioLink] | None = None,
) -> list[Conflict]:
    """PORTFOLIO: the investor's portfolio holds a competitor, or the investor took part in one
    of its rounds (Cala sometimes lacks the portfolio edge). One Conflict per competitor.
    BOARD: a competitor's BOARD member is one of the investor's people (one per competitor+person).
    `rounds`: the competitors' rounds, when the caller already has them; otherwise fetched here.
    `hidden` (B22, core.xray): direct rivals found in the investor's portfolio that are not on
    the competitor list; they conflict through the portfolio link (its sources), listed last.
    `portfolio`: the investor's portfolio, when the caller already has it.
    """
    store = get_store()
    if rounds is None:
        fetched = await asyncio.gather(*(store.rounds(c.company.id) for c in competitors))
        rounds = [rd for rds in fetched for rd in rds]

    given = portfolio

    async def own_portfolio() -> list[PortfolioLink]:
        return given if given is not None else await store.portfolio(investor_id)

    portfolio, investor_people = await asyncio.gather(own_portfolio(), store.people(investor_id))
    by_id = {c.company.id: c for c in competitors}
    by_id |= {c.company.id: c for c in hidden if c.company.id not in by_id}

    portfolio_hits: dict[str, Conflict] = {}

    def backs(company_id: str, sources: list[Source]) -> None:
        comp = by_id.get(company_id)
        if comp is not None:
            new = Conflict(kind="PORTFOLIO", competitor=ref_of(comp))
            hit = portfolio_hits.setdefault(comp.company.id, new)
            hit.sources = merge_sources(hit.sources, sources)

    for link in portfolio:
        backs(link.company.id, link.sources)
    for rd in rounds:
        if any(ri.investor.id == investor_id for ri in rd.investors):
            backs(rd.company_id, rd.sources)

    ours: dict[str, list[Source]] = {}  # investor's person id -> sources of their link to it
    for link in investor_people:
        ours[link.person.id] = merge_sources(ours.get(link.person.id, []), link.sources)

    board: list[Conflict] = []
    if ours:  # nobody at the investor -> no BOARD conflict possible, skip the lookups
        their_people = await asyncio.gather(*(store.people(c.company.id) for c in competitors))
        for comp, links in zip(competitors, their_people, strict=True):
            seen: set[str] = set()
            for link in links:
                pid = link.person.id
                if link.role == "BOARD" and pid in ours and pid not in seen:
                    seen.add(pid)
                    board.append(
                        Conflict(
                            kind="BOARD",
                            competitor=ref_of(comp),
                            via_person=link.person,
                            sources=merge_sources(link.sources, ours[pid]),
                        )
                    )
    return [*portfolio_hits.values(), *board]
