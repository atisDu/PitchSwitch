"""Pitch this week (B23): fresh money for the startup's sector, and the partner to talk to.

(a) Fresh funds: Cala's knowledge search names the funds that just closed for the sector; their
    managers join the Pitch pool even with few deals in Cala ("Fresh fund: ..." with the claim's
    sources), and a fresh fund earns full activity points in the score.
(b) The partner: per top investor, the named partner who leads its deals in the space, from
    sourced press claims. Matched by name against the BOARD members of each direct competitor:
    a match is a BOARD conflict (the partner sits on a rival's board) -> Skip.

Gemini only extracts names from the cited claim texts; a name that does not appear verbatim in
a claim it cites is dropped. Every answer is stored in the graph (per sector, per investor and
sector): asked once, the same answer on every machine. Nothing here ever fails a report.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import Counter
from datetime import date

from pydantic import BaseModel

from agent.llm import structured
from contracts.schemas import Company, Competitor, Conflict, EntityRef, Reason
from core.competitors import shared_graph
from core.conflict import merge_sources, ref_of
from data import get_store
from data.mappers import looks_like_investor, name_key

log = logging.getLogger("core.fresh")

FRESH = "fresh_funds"  # graph: sector key -> {"funds": [{"investor": EntityRef, "reason": Reason}]}
PARTNERS = "partners"  # graph: investor id + sector key -> {"partner": {...}} or {"partner": None}
TOP_PARTNERS = 5  # top Pitch investors whose partner is looked up
MAX_FRESH = 10
MAX_PARTNER_CLAIMS = 2

EXTRACT = """You read numbered claims and copy names out of them; you add nothing. Return only \
names that appear word for word in a claim you cite, with that claim's number."""


class _Named(BaseModel):
    name: str
    claims: list[int]


class _Names(BaseModel):
    names: list[_Named]


_BROAD = {"SOFTWARE_AND_SERVICES"}


def sector_of(company: Company, peers: list[Company] = ()) -> str:
    """The startup's sector in words, from its industry tag; with none (live: Sensofusion), the
    tag most of its competitors and market space share ("aerospace and defense")."""
    tags = [i for i in company.industries if i not in _BROAD] or [
        i for c in peers for i in c.industries if i not in _BROAD
    ]
    tag = Counter(tags).most_common(1)[0][0] if tags else ""
    tag = tag or (company.industries[0] if company.industries else "")
    return tag.replace("_AND_", " and ").replace("_", " ").lower() or "technology"


def _key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


async def _names(claims: list[Reason], ask: str) -> list[tuple[str, list[Reason]]]:
    """(name, the claims that name it) pairs Gemini copied out of `claims`; checked verbatim."""
    if not claims:
        return []
    listing = "\n".join(f"[{n}] {c.text}" for n, c in enumerate(claims, start=1))
    got = await structured(f"{ask}\n\nClaims:\n{listing}", _Names, system=EXTRACT, tier="fast")
    out: list[tuple[str, list[Reason]]] = []
    for item in got.names:
        name = item.name.strip()
        cited = [claims[n - 1] for n in dict.fromkeys(item.claims) if 1 <= n <= len(claims)]
        cited = [c for c in cited if name and name.lower() in c.text.lower()]
        if cited and all(name_key(name) != name_key(seen) for seen, _ in out):
            out.append((name, cited))
    return out


async def _stored(collection: str, doc_id: str) -> dict | None:
    try:
        return await shared_graph().get(collection, doc_id)
    except Exception as exc:
        log.warning("%s read failed: %r", collection, exc)
        return None


async def _store(collection: str, doc_id: str, document: dict) -> None:
    try:
        await shared_graph().put(collection, doc_id, document)
    except Exception as exc:
        log.warning("%s write failed: %r", collection, exc)


# --- (a) fresh funds ------------------------------------------------------------------------


async def fresh_funds(sector: str, today: date | None = None) -> list[tuple[EntityRef, Reason]]:
    """(investor, "Fresh fund: ..." reason) for each firm that just closed a fund for the
    sector (`sector_of`), resolved to a Cala investor. [] on any trouble."""
    year = (today or date.today()).year
    doc_id = _key(sector, str(year), "v2")  # v2 (B26): asked with both phrasings
    doc = await _stored(FRESH, doc_id)
    if doc is None:
        try:
            doc = {"sector": sector, "funds": await _look_up_funds(sector, year)}
        except Exception as exc:
            log.warning("fresh funds for %s skipped: %r", sector, exc)
            return []
        await _store(FRESH, doc_id, doc)
    return [
        (EntityRef.model_validate(f["investor"]), Reason.model_validate(f["reason"]))
        for f in doc.get("funds") or []
    ]


async def _look_up_funds(sector: str, year: int) -> list[dict]:
    store = get_store()
    # B26: two phrasings; live, "closed a new fund" alone found 3 funds and missed Keen's €150M.
    questions = [
        f"Which venture capital firms closed a new fund dedicated to {sector} technology in "
        f"Europe in {year - 1} or {year}? Name each firm, the fund size and when it closed.",
        f"Which venture capital firms announced a first or final close of a new fund for "
        f"{sector} startups in Europe in {year - 1} or {year}?",
    ]
    answers = await asyncio.gather(*(store.sourced_answer(q) for q in questions))
    claims = list({c.text: c for _, cs in answers for c in cs if c.sources}.values())
    named = await _names(
        claims,
        "Copy the name of each venture capital FIRM (the fund manager, not the fund) that "
        "closed or launched a fund. One firm per fund: if a claim names a parent company and "
        "the subsidiary that manages the fund, copy only the one that manages it.",
    )
    funds: list[dict] = []
    for name, cited in named[:MAX_FRESH]:
        hits = await store.resolve(name, "investor")
        hit = next((h for h in hits if looks_like_investor(h) and _same_name(name, h.name)), None)
        if hit is None:
            continue
        reason = Reason(
            text="Fresh fund: " + " ".join(c.text for c in cited),
            sources=merge_sources(*(c.sources for c in cited)),
        )
        funds.append(
            {"investor": hit.model_dump(mode="json"), "reason": reason.model_dump(mode="json")}
        )
    return funds


def _same_name(asked: str, found: str) -> bool:
    """'Keen Venture Partners' ~ 'KEEN VENTURE PARTNERS B.V.'; 'AVP' !~ 'AVP Grup'."""
    a, f = name_key(asked), name_key(found)
    return a == f or (f.startswith(a + "-") and len(a) >= 5)


# --- (b) the partner ------------------------------------------------------------------------


async def lead_partner(
    investor: EntityRef, sector: str, look_up: bool = True, deals: list[str] = ()
) -> dict | None:
    """{"name", "reason": Reason} for the partner who leads the investor's deals in the sector,
    or None. `deals`: names of its companies in the space, asked about by name (B26) so the
    claim says what the partner did. `look_up=False`: only a stored answer (no Cala search,
    no Gemini)."""
    doc_id = _key(investor.id, sector, "v3")  # v3 (B26): asked about its top deal too
    doc = await _stored(PARTNERS, doc_id)
    if doc is None:
        if not look_up:
            return None
        try:
            doc = {"partner": await _look_up_partner(investor, sector, deals)}
        except Exception as exc:
            log.warning("partner of %s skipped: %r", investor.name, exc)
            return None
        await _store(PARTNERS, doc_id, doc)
    return doc.get("partner")


async def _look_up_partner(
    investor: EntityRef, sector: str, deals: list[str] = ()
) -> dict | None:
    # B26: the plain question, plus one about its top deal in the space; their claims merged.
    # (One combined question made Cala explain at length that a deal names no partner, and the
    # extractor then named nobody: live, Maki.vc lost Paavo Räisänen.)
    questions = [f"Which partner at {investor.name} leads its investments in {sector} companies?"]
    if deals:
        questions.append(f"Which partner at {investor.name} led its investment in {deals[0]}?")
    store = get_store()
    answers = await asyncio.gather(*(store.sourced_answer(q) for q in questions))
    claims = [
        c.model_copy(update={"text": _tidy(c.text)})
        for c in {c.text: c for _, cs in answers for c in cs if c.sources}.values()
    ]
    named = await _names(
        claims,
        f"Copy the full name of the person who is a partner at {investor.name} and leads its "
        f"{sector} investments or led one of its deals. At most one person; none if no claim "
        f"names one.",
    )
    if not named:
        return None
    name, cited = named[0]
    if len(name.split()) < 2:  # a first name alone could match anyone's board
        return None

    def telling(c: Reason) -> tuple[bool, bool]:  # a deal named first, a denial last
        text = c.text.lower()
        return (not any(d.lower() in text for d in deals), bool(_DENIAL.search(text)))

    cited = sorted(cited, key=telling)[:MAX_PARTNER_CLAIMS]
    reason = Reason(
        text=f"Partner for your space: {name}. " + " ".join(c.text for c in cited),
        sources=merge_sources(*(c.sources for c in cited)),
    )
    return {"name": name, "reason": reason.model_dump(mode="json")}


_DENIAL = re.compile(r"\b(not|no|without|neither|none)\b")
# Cala's claims cite its own records ("The source with ID 32ba7620-d7b2-...") : noise on a card.
_RECORD_ID = re.compile(r"\s*\(?\b(?:with )?IDs?\s+[0-9a-f][0-9a-f\-\u2011]{7,}\)?", re.I)


def _tidy(text: str) -> str:
    return _RECORD_ID.sub("", text).replace(" ,", ",").strip()


async def board_conflicts(partner: dict, competitors: list[Competitor]) -> list[Conflict]:
    """BOARD conflicts: the partner, by name, sits on a direct competitor's board."""
    store = get_store()
    want = name_key(partner["name"])
    boards = await asyncio.gather(
        *(store.people(c.company.id) for c in competitors), return_exceptions=True
    )
    out: list[Conflict] = []
    why = Reason.model_validate(partner["reason"])
    for comp, links in zip(competitors, boards, strict=True):
        if isinstance(links, BaseException):
            continue
        for link in links:
            if link.role == "BOARD" and name_key(link.person.name) == want:
                out.append(
                    Conflict(
                        kind="BOARD",
                        competitor=ref_of(comp),
                        via_person=link.person,
                        sources=merge_sources(link.sources, why.sources),
                    )
                )
                break
    return out


def partner_reason(partner: dict | None) -> Reason | None:
    return Reason.model_validate(partner["reason"]) if partner else None


async def stored_partner_conflicts(
    investor: EntityRef, company: Company, competitors: list[Competitor], space: list[Company]
) -> list[Conflict]:
    """BOARD conflicts through the investor's partner, if a report already looked them up
    (investor check, agent and MCP tools: no Cala search or Gemini call here)."""
    sector = sector_of(company, [*(c.company for c in competitors), *space])
    partner = await lead_partner(investor, sector, look_up=False)
    return await board_conflicts(partner, competitors) if partner else []
