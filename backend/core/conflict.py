"""check_conflict (B4 PORTFOLIO, B5 BOARD): does an investor have a stake in a direct competitor?

Plain set logic over store data; every Conflict carries the sources of the edges it rests on.
"""

from __future__ import annotations

from contracts.schemas import Competitor, Conflict, EntityRef
from data import get_store


def _ref(c: Competitor) -> EntityRef:
    co = c.company
    return EntityRef(id=co.id, name=co.name, type=co.type, description=co.description)


async def check_conflict(investor_id: str, competitors: list[Competitor]) -> list[Conflict]:
    """PORTFOLIO: the investor's portfolio contains a competitor. One Conflict per competitor."""
    by_id = {c.company.id: c for c in competitors}
    conflicts: dict[str, Conflict] = {}
    for link in await get_store().portfolio(investor_id):
        comp = by_id.get(link.company.id)
        if comp is None:
            continue
        new = Conflict(kind="PORTFOLIO", competitor=_ref(comp))
        hit = conflicts.setdefault(comp.company.id, new)
        hit.sources += [s for s in link.sources if s not in hit.sources]
    return list(conflicts.values())
