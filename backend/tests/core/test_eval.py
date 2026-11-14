"""B8 eval set: known facts about the demo cases (contracts/fixtures/README.md) the logic must find.

Runs on whatever `get_store()` returns: the fake store by default, live Cala with
USE_FAKE_STORE=false (B9). Competitors are fixed per case so scoring and conflicts are judged
without Gemini; the Gemini judge has its own case, skipped while GEMINI_API_KEY is empty.
"""

import os
from datetime import date

import pytest

from contracts.schemas import Competitor, FounderReport
from core.briefs import collect_facts
from core.competitors import find_competitors
from core.conflict import check_conflict
from core.scoring import rank_investors
from data import get_store
from data.config import load_env

load_env()  # the live-Gemini skipif below reads GEMINI_API_KEY at import time

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
SENSOFUSION = "202e9283-6455-486f-8868-03c7e0d0cf29"
STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
NESTAI = "14359613-a45f-4804-892d-3b9dd9e927a9"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"  # NATO Innovation Fund
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"
TESI = "df5be140-d50e-4e21-bb4f-d8f1e4ad3959"
STENDR_BACKERS = {
    "0322aa66-c3c7-470c-a940-e6ec117d4051",  # Rainfall Ventures
    "9b65ed62-a126-4255-8339-44c59fbf0ad8",  # Skyfall Ventures
    "3ef31033-9773-4fbd-91bf-1a971554e683",  # Startuplab Founders
}
ANGEL = "c75cbef9-0ab0-5552-84f8-fc59bc63ea93"  # Tuomas Rasila, a person: in Kova Labs's pre-seed
KOVA = "b7226c97-3a44-5176-8544-cb91246b2249"  # Kova Labs
TODAY = date(2026, 11, 13)


@pytest.fixture
def store():
    get_store.cache_clear()  # pick up USE_FAKE_STORE from the environment / .env
    yield get_store()
    get_store.cache_clear()


async def founder(store, company_id: str, *rivals: str) -> FounderReport:
    """Rivals fixed per case; the market space = the store's candidates (judge not involved)."""
    company = await store.company(company_id)
    competitors = [Competitor(company=await store.company(i), reason="eval") for i in rivals]
    space = await store.candidate_competitors(company)
    return await rank_investors(company, competitors, space, today=TODAY)


def by_id(report: FounderReport):
    return {s.investor.id: s for s in report.pitch + report.skip}


async def test_kelluu_series_a_lead_is_nato_innovation_fund(store):
    """Kelluu's Series A was led by NIF: for a Kelluu rival, NIF is a Skip with a known lead."""
    nif = by_id(await founder(store, STENDR, KELLUU, SENSOFUSION))[NIF]
    assert nif.conflicts and nif.conflicts[0].competitor.id == KELLUU
    assert nif.leads_in_space >= 1 and nif.lead_data in ("known", "partial")
    assert nif.last_lead_date and nif.last_lead_date.startswith("2026")
    assert any("Led" in r.text and r.sources for r in nif.reasons)


async def test_maki_leads_defence_pre_seeds(store):
    """Maki.vc led the Aavuus and Metaktik pre-seeds: a top Pitch for a defence startup."""
    report = await founder(store, KELLUU, STENDR, NESTAI)
    maki = by_id(report)[MAKI]
    assert not maki.conflicts and maki in report.pitch[:3]
    assert maki.leads_in_space >= 2
    assert any("Pre-Seed" in r.text and r.sources for r in maki.reasons)


async def test_tesi_backs_kelluu_conflict_for_rival(store):
    """Tesi backs Kelluu: checking Tesi for a Kelluu rival shows a sourced PORTFOLIO conflict."""
    rivals = [Competitor(company=await store.company(KELLUU), reason="eval")]
    conflicts = await check_conflict(TESI, rivals)
    assert [(c.kind, c.competitor.id) for c in conflicts] == [("PORTFOLIO", KELLUU)]
    assert conflicts[0].sources


async def test_counter_drone_conflict(store):
    """The demo's conflict moment: Stendr's backers are Skip for Sensofusion (via A7's undated
    backers round, since Cala has no round details for Stendr)."""
    report = await founder(store, SENSOFUSION, STENDR, KELLUU)
    skipped = {s.investor.id: s for s in report.skip}
    hits = STENDR_BACKERS & set(skipped)
    assert hits == STENDR_BACKERS
    assert all(any(c.competitor.id == STENDR for c in skipped[i].conflicts) for i in hits)


@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="live Gemini: no API key")
async def test_gemini_judges_counter_drone_rivals(store):
    """Live Gemini: Stendr (counter-drone) is a direct competitor of Sensofusion."""
    found = await find_competitors(await store.company(SENSOFUSION))
    assert STENDR in {c.company.id for c in found}
    assert all(c.reason for c in found)


async def test_angel_is_an_investor_like_any_other(store):
    """Contract 1.1.1: a person who invests can be ranked, checked and briefed. Tuomas Rasila
    took part in Kova Labs's pre-seed: a Pitch for Kelluu while Kova Labs is only in its market
    space, a Skip with a sourced conflict once Kova Labs is the direct competitor."""
    assert (await store.company(ANGEL)).type == "Person"

    as_pitch = await founder(store, KELLUU, STENDR)
    angel = by_id(as_pitch)[ANGEL]
    assert angel in as_pitch.pitch and not angel.conflicts and angel.rounds_in_space >= 1

    as_skip = await founder(store, KELLUU, KOVA)
    hit = by_id(as_skip)[ANGEL]
    assert hit in as_skip.skip
    assert hit.conflicts[0].competitor.id == KOVA and hit.conflicts[0].sources

    # the investor check and the brief take the same ID
    assert [c.competitor.id for c in await check_conflict(ANGEL, as_skip.competitors)] == [KOVA]
    kelluu = await store.company(KELLUU)
    name, facts = await collect_facts(ANGEL, kelluu, as_skip.competitors, [])
    assert name == "Tuomas Rasila" and all(f.sources for f in facts)
    assert any(f.text.startswith("Conflict: Tuomas Rasila backs Kova Labs") for f in facts)
