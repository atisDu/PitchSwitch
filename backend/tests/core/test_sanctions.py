"""B25 sanctions screen on the fake store, with scripted sanctions records."""

from datetime import date

import pytest

import core.sanctions as sanctions
from contracts.schemas import Conflict, EntityRef, Reason, Source
from core.briefs import conflict_fact
from core.scoring import rank_investors
from data import Upstream, get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
TODAY = date(2026, 11, 13)
EURLEX = Source(name="The European Data Portal", url="https://eur-lex.europa.eu/x")
RECORD = Reason(text="Sanctioned: EU.7808.66 (EU), since 2023-03-15", sources=[EURLEX])


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


def records(
    monkeypatch, store, sanctioned: set[str], lps: dict[str, list[EntityRef]] | None = None
):
    async def fake_sanctions(id):
        return [RECORD] if id in sanctioned else []

    async def fake_lps(id):
        return (lps or {}).get(id, [])

    monkeypatch.setattr(store, "sanctions", fake_sanctions)
    monkeypatch.setattr(store, "limited_partners", fake_lps)


FUND = EntityRef(id="fund", name="Some Fund", type="Organization")
LP = EntityRef(id="lp", name="Bad LP", type="Organization")


async def test_a_record_on_the_fund_or_an_lp_is_a_sanction_conflict(store, monkeypatch):
    records(monkeypatch, store, {"fund"})
    own = await sanctions.screen(FUND)
    assert [(c.kind, c.competitor.id, c.sources) for c in own.conflicts] == [
        ("SANCTION", "fund", [EURLEX])
    ]
    assert (
        own.reasons[0].text == "Conflict: Some Fund has a sanctions record in Cala: " + RECORD.text
    )

    records(monkeypatch, store, {"lp"}, {"fund": [LP, FUND]})  # the fund itself is no LP of its own
    via_lp = await sanctions.screen(FUND)
    assert [c.competitor.id for c in via_lp.conflicts] == ["lp"]
    assert via_lp.reasons[0].text.startswith("Conflict: its LP Bad LP has a sanctions record")


async def test_no_record_says_screened_never_clean(store, monkeypatch):
    records(monkeypatch, store, set(), {"fund": [LP]})
    got = await sanctions.screen(FUND)
    assert got.conflicts == []
    assert [r.text for r in got.reasons] == ["screened: no sanctions record in Cala"]


async def test_cala_trouble_means_not_screened(store, monkeypatch):
    async def down(id):
        raise Upstream("CACHE_ONLY is on and POST /entities/x is not cached")

    monkeypatch.setattr(store, "sanctions", down)
    got = await sanctions.screen(FUND)
    assert got.conflicts == [] and got.reasons == []  # neither a hit nor "screened"


async def test_report_skips_a_sanctioned_investor(store, monkeypatch):
    company = await store.company(KELLUU)
    space = await store.candidate_competitors(company)
    base = await rank_investors(company, [], space, today=TODAY)
    target = base.pitch[0].investor
    records(monkeypatch, store, {target.id})

    after = await rank_investors(company, [], space, today=TODAY, screen=True)

    hit = next(s for s in after.skip if s.investor.id == target.id)
    assert [c.kind for c in hit.conflicts] == ["SANCTION"]
    assert hit.reasons[0].text.startswith("Score ")  # the breakdown stays first
    assert any("has a sanctions record in Cala" in r.text for r in hit.reasons)
    others = [s for s in after.pitch if s.reasons]
    assert others and all(
        any(r.text == "screened: no sanctions record in Cala" for r in s.reasons) for s in others
    )


def test_a_brief_states_the_sanction_not_a_competitor():
    own = Conflict(kind="SANCTION", competitor=FUND, sources=[EURLEX])
    assert conflict_fact(own, "Some Fund", "Kelluu").text == (
        "Conflict: Cala has a sanctions record on Some Fund."
    )
    lp = Conflict(kind="SANCTION", competitor=LP, sources=[EURLEX])
    assert "(its LP Bad LP)" in conflict_fact(lp, "Some Fund", "Kelluu").text
