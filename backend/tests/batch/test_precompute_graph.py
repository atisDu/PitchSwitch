"""The batch crawl on recorded Cala responses: what it stores, and that it can be rerun."""

import pytest

from batch.precompute_graph import CRAWLED, crawl, crawl_investor, investors_by_country
from cache.graph import FileGraph, MemoryGraph
from contracts.schemas import Company, EntityRef, PortfolioLink, Round
from data.errors import Upstream
from data.store import CalaDataStore
from tests.data.conftest import RecordedCala

TESI = "df5be140-d50e-4e21-bb4f-d8f1e4ad3959"
NATO = "2ca07622-990d-40bf-a4fe-36434d43d6db"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def cala():
    return RecordedCala()


@pytest.fixture
def store(cala):
    return CalaDataStore(cala)


async def test_crawl_stores_each_investor_behind_the_seed_and_its_candidates(store):
    graph = MemoryGraph()
    counts = await crawl(store, graph, seeds=["Kelluu"], countries=[], clock=Clock())

    stored = await graph.ids(CRAWLED)
    assert {TESI, NATO, MAKI} <= set(stored)  # Kelluu's backers, and Maki.vc via Aavuus
    assert counts["found"] == counts["crawled"] + counts["failed"] and counts["skipped"] == 0
    assert counts["crawled"] >= 5

    tesi = await graph.get(CRAWLED, TESI)
    assert tesi["name"] == "Tesi" and tesi["crawled_at"] == 1_000_000.0
    assert Company.model_validate(tesi["investor"]).type == "Organization"
    portfolio = [PortfolioLink.model_validate(link) for link in tesi["portfolio"]]
    rounds = [Round.model_validate(item) for item in tesi["rounds"]]
    assert len(portfolio) >= 40 and rounds
    assert all(any(i.investor.id == TESI for i in item.investors) for item in rounds)


async def test_a_second_run_skips_fresh_investors_until_they_are_a_day_old(store):
    graph, clock = MemoryGraph(), Clock()
    first = await crawl(store, graph, seeds=["Kelluu"], countries=[], clock=clock)

    clock.now += 60 * 60
    second = await crawl(store, graph, seeds=["Kelluu"], countries=[], clock=clock)
    assert second["skipped"] == first["crawled"] and second["crawled"] == 0

    clock.now += 24 * 60 * 60
    third = await crawl(store, graph, seeds=["Kelluu"], countries=[], clock=clock)
    assert third["crawled"] == first["crawled"]
    assert (await graph.get(CRAWLED, TESI))["crawled_at"] == clock.now


async def test_a_failing_investor_is_recorded_and_retried_next_time(store, cala):
    graph, clock = MemoryGraph(), Clock()
    real_entity = cala.entity
    broken = True

    async def flaky(entity_id, **projection):
        if entity_id == NATO and broken:
            raise Upstream("Cala timed out")
        return await real_entity(entity_id, **projection)

    cala.entity = flaky
    ref = EntityRef(id=NATO, name="NATO Innovation Fund", type="Organization")
    assert await crawl_investor(store, graph, ref, now=clock()) == "failed"
    assert (await graph.get(CRAWLED, NATO))["error"] == "Cala timed out"

    broken = False
    assert await crawl_investor(store, graph, ref, now=clock()) == "crawled"  # not skipped
    assert "error" not in await graph.get(CRAWLED, NATO)
    assert await crawl_investor(store, graph, ref, now=clock()) == "skipped"
    assert await crawl_investor(store, graph, ref, now=clock(), force=True) == "crawled"


async def test_max_investors_caps_the_work_and_unknown_seeds_are_skipped(store):
    graph = MemoryGraph()
    counts = await crawl(
        store, graph, seeds=["No Such Firm", "Kelluu"], countries=[], max_investors=3, clock=Clock()
    )
    assert counts["found"] > 3 and len(await graph.ids(CRAWLED)) == 3


async def test_investors_by_country_keeps_named_organisations():
    asked = []

    class FakeCala:
        async def query(self, text):
            asked.append(text)
            if "Finland" not in text:
                raise Upstream("too complex")
            return {
                "results": [{"name": "Maki.vc", "description": "VC"}, {"name": "No Entity"}],
                "entities": [
                    {"id": "m1", "name": "Maki.vc", "entity_type": "Company", "mentions": []},
                    {"id": "p1", "name": "Some Person", "entity_type": "Person"},
                    {"id": "x1", "name": "Unrelated Oy", "entity_type": "Company"},
                    {"id": "f1", "name": "Finland", "entity_type": "Country"},
                ],
            }

    found = await investors_by_country(FakeCala(), ["Finland", "Sweden"])
    assert list(found) == ["m1"] and found["m1"].name == "Maki.vc"
    assert len(asked) == 2 and "based in Finland" in asked[0]


async def test_graph_backends_store_and_list_documents(tmp_path):
    for graph in (MemoryGraph(), FileGraph(tmp_path / "graph")):
        assert await graph.get("investor_graph", "a") is None
        assert await graph.ids("investor_graph") == []
        await graph.put("investor_graph", "b", {"n": 2, "names": ["ö"]})
        await graph.put("investor_graph", "a", {"n": 1})
        await graph.put("investor_graph", "a", {"n": 3})
        await graph.put("other", "z", {})
        assert await graph.get("investor_graph", "a") == {"n": 3}
        assert await graph.get("investor_graph", "b") == {"n": 2, "names": ["ö"]}
        assert await graph.ids("investor_graph") == ["a", "b"]
