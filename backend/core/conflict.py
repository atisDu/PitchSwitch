"""check_conflict (B4 PORTFOLIO, B5 BOARD): does an investor have a stake in a direct competitor?

Plain set logic over store data; every Conflict carries the sources of the edges it rests on.
"""

from __future__ import annotations

import asyncio

from contracts.schemas import Competitor, Conflict, EntityRef, Source
from data import get_store


def _ref(c: Competitor) -> EntityRef:
    co = c.company
    return EntityRef(id=co.id, name=co.name, type=co.type, description=co.description)


def _union(*lists: list[Source]) -> list[Source]:
    out: list[Source] = []
    for sources in lists:
        out += [s for s in sources if s not in out]
    return out


async def check_conflict(investor_id: str, competitors: list[Competitor]) -> list[Conflict]:
    """PORTFOLIO: the investor's portfolio holds a competitor (one Conflict per competitor).
    BOARD: a competitor's BOARD member is one of the investor's people (one per competitor+person).
    """
    store = get_store()
    portfolio, investor_people = await asyncio.gather(
        store.portfolio(investor_id), store.people(investor_id)
    )
    by_id = {c.company.id: c for c in competitors}

    portfolio_hits: dict[str, Conflict] = {}
    for link in portfolio:
        comp = by_id.get(link.company.id)
        if comp is not None:
            new = Conflict(kind="PORTFOLIO", competitor=_ref(comp))
            hit = portfolio_hits.setdefault(comp.company.id, new)
            hit.sources = _union(hit.sources, link.sources)

    ours: dict[str, list[Source]] = {}  # investor's person id -> sources of their link to it
    for link in investor_people:
        ours[link.person.id] = _union(ours.get(link.person.id, []), link.sources)

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
                            competitor=_ref(comp),
                            via_person=link.person,
                            sources=_union(link.sources, ours[pid]),
                        )
                    )
    return [*portfolio_hits.values(), *board]
