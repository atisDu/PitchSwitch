"""Report notes (B24, contract 1.2.0 `FounderReport.notes`): sourced lines about the direct
competitors that belong to no single investor.

- Grants they won: non-dilutive money the founder can go for too (NATO DIANA, EDF, EIC).
- Which of them attend Slush 2026: who the founder will meet on the floor.

One Cala knowledge search each, naming the competitors. Gemini only copies, for each claim that
says a competitor won a grant / attends Slush 2026, that competitor's name out of the claim; the
name must appear in the claim and be one of the competitors. Stored per startup and competitor
list: asked once. Never fails a report (no notes instead).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

from contracts.schemas import Company, Competitor, Reason
from core.fresh import _names, _store, _stored
from data import get_store
from data.mappers import name_key

log = logging.getLogger("core.notes")

NOTES = "report_notes"  # graph: startup + competitor ids -> {"notes": [Reason]}
MAX_COMPETITORS = 8  # named in each question
MAX_NOTES = 8

GRANTS = (
    "Which of these companies won grants or public funding from NATO DIANA, the European Defence "
    "Fund (EDF), the European Innovation Council (EIC) or a national defence innovation "
    "programme: {names}? Name the programme, the year and the amount."
)
SLUSH = "Which of these companies are attending, exhibiting or pitching at Slush 2026: {names}?"


def _short(name: str) -> str:
    """'MYDEFENCE GROUP APS' -> 'mydefence group'; used to spot the name inside a claim."""
    return name_key(name).replace("-", " ")


def _matches(said: str, competitor: Company) -> bool:
    a, c = _short(said), _short(competitor.name)
    return bool(a) and (a == c or c.startswith(a + " ") or a.startswith(c + " "))


async def _notes_for(
    question: str, prefix: str, ask: str, competitors: list[Competitor]
) -> list[Reason]:
    names = ", ".join(c.company.name for c in competitors)
    _, claims = await get_store().sourced_answer(question.format(names=names))
    claims = [c for c in claims if c.sources]
    out: list[Reason] = []
    done: set[str] = set()  # one note per competitor and topic (Cala often repeats a fact)
    for said, cited in await _names(claims, ask):
        rival = next((c for c in competitors if _matches(said, c.company)), None)
        if rival is None or rival.company.id in done:
            continue  # not a direct competitor (Cala's answer brought it up), or already noted
        done.add(rival.company.id)
        out.append(Reason(text=f"{prefix}{cited[0].text}", sources=cited[0].sources))
    return out


async def report_notes(company: Company, competitors: list[Competitor]) -> list[Reason]:
    rivals = competitors[:MAX_COMPETITORS]
    if not rivals:
        return []
    ids = " ".join(sorted(c.company.id for c in rivals))
    doc_id = hashlib.sha256(f"{company.id}|{ids}".encode()).hexdigest()[:16]
    doc = await _stored(NOTES, doc_id)
    if doc is None:
        try:
            grants, slush = await asyncio.gather(
                _notes_for(
                    GRANTS,
                    "Non-dilutive: ",
                    "Copy the company name from each claim that says the company WON or "
                    "RECEIVED a grant or public funding. Leave out claims that say it did not.",
                    rivals,
                ),
                _notes_for(
                    SLUSH,
                    "At Slush 2026: ",
                    "Copy the company name from each claim that says the company WILL ATTEND, "
                    "exhibit or pitch at Slush 2026. Leave out claims that say it will not, or "
                    "that no information was found.",
                    rivals,
                ),
            )
        except Exception as exc:
            log.warning("report notes for %s skipped: %r", company.name, exc)
            return []
        doc = {"notes": [n.model_dump(mode="json") for n in [*grants, *slush][:MAX_NOTES]]}
        await _store(NOTES, doc_id, doc)
    return [Reason.model_validate(n) for n in doc.get("notes") or []]
