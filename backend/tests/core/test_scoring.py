"""rank_investors on the fake store, competitors given (no Gemini)."""

import re
from datetime import date

import pytest

import core.scoring as scoring
from contracts.schemas import Competitor, EntityRef, Round, RoundInvestor, Source
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


async def test_score_breakdown_adds_up_to_the_score(store):
    r = await report(store, STENDR, KELLUU, SENSOFUSION)
    for s in r.pitch + r.skip:
        if not s.rounds_in_space:
            continue
        head = s.reasons[0].text
        assert head.startswith(f"Score {round(s.score, 1):g}/100 = ")
        parts = [float(re.search(r"([\d.]+)/\d+ \(", p)[1]) for p in head.split(" + ")]
        assert len(parts) == len(WEIGHTS) and abs(sum(parts) - s.score) < 0.2


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


# --- scoring v2 (B18), on made-up rounds ---------------------------------------------------------

TODAY = date(2026, 11, 14)
ME = EntityRef(id="me", name="Me Ventures", type="Organization")
SRC = [Source(name="press", url="https://example.com")]


def rd(rid, company, others=0, lead=None, label="Seed", when="2026-06-01"):
    """A round of `company` with ME (is_lead=lead) and `others` more investors (lead unknown)."""
    crowd = [RoundInvestor(investor=EntityRef(id=f"o{i}", name="O", type="Organization"))
             for i in range(others)]
    me = RoundInvestor(investor=ME, is_lead=lead)
    return Round(id=rid, company_id=company, label=label, date=when, investors=[me, *crowd],
                 sources=SRC)


def score(rounds, history=()):
    return scoring._score(ME, rounds, list(history), [], [], lambda r: r.id, TODAY)


def test_unknown_lead_earns_a_share_of_a_lead():
    s = score([rd("r1", "c1", others=3)])  # 4 investors, nobody marked as lead: 1/4 of a lead
    assert s.leads_in_space == 0 and s.lead_data == "unknown"
    assert "leads 3.8/30 (0 led, 0.2 likely)" in s.reasons[0].text  # 30 * 0.25 / 2


def test_companies_not_rounds_and_backers_count_half():
    three_in_one = score([rd(f"r{i}", "c1", lead=False) for i in range(3)])
    backers = score([rd("c2:backers", "c2", lead=False, label=None, when=None)])
    assert "companies here 6.7/20 (1)" in three_in_one.reasons[0].text
    assert "companies here 3.3/20 (0.5)" in backers.reasons[0].text


def test_recency_only_from_rounds_in_the_space():
    outside_lead = rd("x", "elsewhere", lead=True, when="2026-10-01")
    s = score([rd("c2:backers", "c2", label=None, when=None)], history=[outside_lead])
    assert s.last_lead_date == "2026-10-01"  # still shown on the card
    assert "recency 0/15 (no dated round here)" in s.reasons[0].text


def test_activity_counts_and_breaks_ties():
    busy = score([rd("r", "c1", lead=False)], history=[rd(f"h{i}", f"x{i}") for i in range(6)])
    idle = score([rd("r", "c1", lead=False)])
    assert "activity 15/15 (7 in 12 mo)" in busy.reasons[0].text
    assert busy.score > idle.score


def test_activity_needs_a_company_in_the_space():
    busy_elsewhere = score([], history=[rd(f"h{i}", f"x{i}") for i in range(6)])
    assert busy_elsewhere.score == 0 and busy_elsewhere.deals_last_12m == 6

