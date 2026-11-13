"""check_conflict on the fake store (fixture data, no network)."""

import pytest

from contracts.schemas import Competitor
from core.conflict import check_conflict
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"  # NATO Innovation Fund: led Kelluu's Series A
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


async def rivals(store, *ids):
    return [Competitor(company=await store.company(i), reason="test") for i in ids]


async def test_portfolio_conflict_with_sources(store):
    out = await check_conflict(NIF, await rivals(store, KELLUU, STENDR))
    assert [(c.kind, c.competitor.id) for c in out] == [("PORTFOLIO", KELLUU)]
    assert out[0].competitor.name.startswith("Kelluu")
    assert out[0].sources and len(out[0].sources) == len(set(map(repr, out[0].sources)))


async def test_no_conflict_when_competitor_not_in_portfolio(store):
    assert await check_conflict(MAKI, await rivals(store, KELLUU)) == []


async def test_no_competitors_or_unknown_investor(store):
    assert await check_conflict(NIF, []) == []
    assert await check_conflict("unknown-investor", await rivals(store, KELLUU)) == []
