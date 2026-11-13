"""rank_investors on the fake store, competitors given (no Gemini)."""

from datetime import date

import pytest

import core.scoring as scoring
from contracts.schemas import Competitor
from core.competitors import Judgement
from core.scoring import CAPS, WEIGHTS, parse_date, rank_investors
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
SENSOFUSION = "202e9283-6455-486f-8868-03c7e0d0cf29"
STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
NESTAI = "14359613-a45f-4804-892d-3b9dd9e927a9"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"
TODAY = date(2026, 11, 13)


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


async def report(store, company_id, *rival_ids):
    """Rivals as given; the whole fixture candidate list as the market space."""
    company = await store.company(company_id)
    rivals = [Competitor(company=await store.company(i), reason="test") for i in rival_ids]
    space = await store.candidate_competitors(company)
    return await rank_investors(company, rivals, space, today=TODAY)


def test_weights_add_up_to_100():
    assert sum(WEIGHTS.values()) == 100
    assert set(CAPS) <= set(WEIGHTS)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("2026-04-14", date(2026, 4, 14)),
        ("2025-10", date(2025, 10, 1)),
        ("2026", date(2026, 1, 1)),
        ("2026-04-14T10:00:00Z", date(2026, 4, 14)),
        (None, None),
        ("", None),
        ("Oct 2025", None),
        ("2025-13", None),
    ],
)
def test_parse_date(text, want):
    assert parse_date(text) == want


async def test_backer_of_direct_competitor_is_skipped_with_lead(store):
    r = await report(store, STENDR, KELLUU, SENSOFUSION)
    nif = next(s for s in r.skip if s.investor.id == NIF)
    assert [c.competitor.id for c in nif.conflicts] == [KELLUU]
    assert nif.conflicts[0].sources
    assert nif.leads_in_space == 1 and nif.lead_data == "known"
    assert nif.last_lead_date == "2026-04-14"


async def test_report_invariants(store):
    r = await report(store, STENDR, KELLUU, SENSOFUSION)
    assert r.pitch and r.skip
    assert all(not s.conflicts for s in r.pitch) and all(s.conflicts for s in r.skip)
    for side in (r.pitch, r.skip):
        assert [s.score for s in side] == sorted((s.score for s in side), reverse=True)
        assert all(0 <= s.score <= 100 for s in side)
        assert all(reason.sources for s in side for reason in s.reasons)
    ids = [s.investor.id for s in r.pitch + r.skip]
    assert len(ids) == len(set(ids)) and STENDR not in ids


async def test_similar_but_not_direct_space_lands_in_pitch(store):
    """Maki.vc led Aavuus + Metaktik pre-seeds: not direct rivals of Stendr here -> Pitch, top."""
    r = await report(store, STENDR, KELLUU, SENSOFUSION)
    assert r.pitch[0].investor.id == MAKI
    assert r.pitch[0].leads_in_space == 2


async def test_current_investors_left_out_and_warm_paths_found(store):
    r = await report(store, KELLUU, STENDR, NESTAI)
    current = {ri.investor.id for rd in await store.rounds(KELLUU) for ri in rd.investors}
    ids = {s.investor.id for s in r.pitch + r.skip}
    assert NIF in current and not ids & current
    assert any(s.warm_paths for s in r.pitch)
    assert len(r.pitch) <= 3 + scoring.MAX_CO_INVESTORS + 10


async def test_round_without_portfolio_edge_still_conflicts(store, monkeypatch):
    async def no_portfolio(_investor_id):
        return []

    monkeypatch.setattr(store, "portfolio", no_portfolio)
    r = await report(store, STENDR, KELLUU, SENSOFUSION)
    nif = next(s for s in r.skip if s.investor.id == NIF)
    kelluu_round = (await store.rounds(KELLUU))[0]
    assert nif.conflicts[0].kind == "PORTFOLIO"
    assert nif.conflicts[0].sources == kelluu_round.sources


async def test_asks_the_judge_when_not_given(store, monkeypatch):
    called = {}

    async def fake_judge(company):
        called["id"] = company.id
        return Judgement(direct=[], space=[])

    monkeypatch.setattr(scoring, "judge", fake_judge)
    r = await rank_investors(await store.company(STENDR), today=TODAY)
    assert called["id"] == STENDR and r.competitors == [] and r.skip == []


async def test_unrelated_candidates_do_not_feed_pitch(store):
    """Only the judged market space counts: without Aavuus/Metaktik in it, Maki.vc's pre-seed
    leads there are not counted (it may still show up as a co-investor of Stendr's backers)."""
    company = await store.company(STENDR)
    rivals = [Competitor(company=await store.company(KELLUU), reason="test")]
    narrow = await rank_investors(company, rivals, [], today=TODAY)
    maki = [s for s in narrow.pitch if s.investor.id == MAKI]
    assert all(s.rounds_in_space == 0 and s.leads_in_space == 0 for s in maki)
    assert NIF in {s.investor.id for s in narrow.skip}
