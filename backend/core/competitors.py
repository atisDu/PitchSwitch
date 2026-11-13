"""find_competitors (B3): the store's candidates, judged by Gemini down to the direct competitors.

Gemini only picks among candidate IDs and writes a one-line reason; any ID it invents is dropped.
"""

from __future__ import annotations

from pydantic import BaseModel

from agent.llm import structured
from contracts.schemas import Company, Competitor
from data import get_store

MAX_COMPETITORS = 15

SYSTEM = """You judge which companies are DIRECT competitors of a startup, for a founder deciding \
which investors to pitch (an investor who backed a direct competitor has a conflict).
A direct competitor sells a similar product or service to similar customers. Same broad industry \
alone is not enough; investors, funds, agencies and suppliers are never competitors.
Use only the descriptions given. Return at most 15, the most direct first; return fewer (or none) \
if fewer qualify. Use only IDs from the candidate list, copied exactly. Each reason is one short \
factual sentence on what overlaps, with no numbers, dates or names not in the descriptions."""


class _Pick(BaseModel):
    id: str
    reason: str


class _Judgement(BaseModel):
    competitors: list[_Pick]


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


async def find_competitors(company: Company, k: int = 30) -> list[Competitor]:
    candidates = [
        c for c in await get_store().candidate_competitors(company, k) if c.id != company.id
    ]
    if not candidates:
        return []
    by_id = {c.id: c for c in candidates}
    prompt = (
        f"Startup:\n{_line(company)}\n\n"
        f"Candidates:\n" + "\n".join(_line(c) for c in by_id.values())
    )
    judged = await structured(prompt, _Judgement, system=SYSTEM)

    out: list[Competitor] = []
    for pick in judged.competitors:
        c = by_id.pop(pick.id.strip(), None)  # pop: unknown and repeated IDs are both dropped
        if c is not None:
            out.append(Competitor(company=c, reason=pick.reason.strip()))
    return out[:MAX_COMPETITORS]
