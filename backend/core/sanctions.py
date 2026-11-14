"""Sanctions screen (B25): every ranked investor and its LPs against Cala's sanctions records.

ID-based and sourced (Cala's IS_SUBJECT_OF_SANCTION edge, via `DataStore.sanctions()`): a record
on the investor or on one of its LPs (`DataStore.limited_partners()`) is a SANCTION conflict
(contract 1.2.0) with the record as source, so the investor goes to Skip. Screened with no record:
the reason "screened: no sanctions record in Cala" (never "clean": Cala not having one is not
proof). An investor that could not be screened (Cala trouble, cache-only miss) gets neither.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from contracts.schemas import Conflict, EntityRef, Reason
from data import get_store
from data.errors import DataError

log = logging.getLogger("core.sanctions")

NO_RECORD = "screened: no sanctions record in Cala"  # exact wording (contract 1.2.0, C)
MAX_LPS = 5  # LPs screened per investor


@dataclass
class Screen:
    conflicts: list[Conflict] = field(default_factory=list)
    reasons: list[Reason] = field(default_factory=list)


async def screen(investor: EntityRef) -> Screen:
    store = get_store()
    try:
        own, lps = await asyncio.gather(
            store.sanctions(investor.id), store.limited_partners(investor.id)
        )
        lps = [lp for lp in lps if lp.id != investor.id][:MAX_LPS]
        theirs = await asyncio.gather(*(store.sanctions(lp.id) for lp in lps))
    except DataError as exc:
        log.warning("sanctions screen of %s skipped: %s", investor.name, exc)
        return Screen()
    out = Screen()
    hits = [(investor, r, None) for r in own] + [
        (lp, r, lp) for lp, records in zip(lps, theirs, strict=True) for r in records
    ]
    for entity, record, lp in hits:
        out.conflicts.append(Conflict(kind="SANCTION", competitor=entity, sources=record.sources))
        who = f"its LP {lp.name}" if lp else investor.name
        out.reasons.append(
            Reason(
                text=f"Conflict: {who} has a sanctions record in Cala: {record.text}",
                sources=record.sources,
            )
        )
    if not hits:
        out.reasons.append(Reason(text=NO_RECORD))
    return out


async def screen_all(investors: list[EntityRef]) -> dict[str, Screen]:
    got = await asyncio.gather(*(screen(i) for i in investors))
    return {i.id: s for i, s in zip(investors, got, strict=True)}


def sanction_fact(c: Conflict, investor: str) -> Reason:
    """A SANCTION conflict as a brief fact."""
    whose = "" if c.competitor.name == investor else f" (its LP {c.competitor.name})"
    return Reason(
        text=f"Conflict: Cala has a sanctions record on {investor}{whose}.", sources=c.sources
    )
