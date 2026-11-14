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
    return CalaDataStore(cala, graph=MemoryGraph())


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


# --- derive (A15) --------------------------------------------------------------------------------


def ref(investor_id, name):
    return {"id": investor_id, "name": name, "type": "Organization", "description": None}


def link(investor_id, company_id):
    return {"investor_id": investor_id, "company": ref(company_id, company_id), "sources": []}


def deal(round_id, company_id, date, label, *investors):
    return {
        "id": round_id,
        "company_id": company_id,
        "label": label,
        "date": date,
        "amount_text": None,
        "amount_eur": None,
        "investors": [{"investor": ref(i, n), "is_lead": lead} for i, n, lead in investors],
        "sources": [],
    }


async def crawled_graph():
    from batch.precompute_graph import CRAWLED as crawled

    graph = MemoryGraph()
    a_round = deal("r1", "c1", "2026-04-14", "Series A", ("A", "Alpha", True), ("B", "Beta", False))
    old_round = deal(
        "r2", "c2", "2023-01-10", "Seed", ("A", "Alpha", None), ("X", "Outsider", True)
    )
    twin_round = deal(
        "r3", "c3", "2026-09-01", "Seed", ("B", "Beta", True), ("A2", "ALPHA Oy", False)
    )
    documents = {
        "A": {"portfolio": [link("A", "c1"), link("A", "c9")], "rounds": [a_round, old_round]},
        "B": {"portfolio": [link("B", "c1"), link("B", "c9")], "rounds": [a_round, twin_round]},
        "C": {"portfolio": [link("C", "c7")], "rounds": []},
    }
    names = {"A": "Alpha", "B": "Beta", "C": "Gamma"}
    for investor_id, document in documents.items():
        document.update(name=names[investor_id], investor=ref(investor_id, names[investor_id]))
        await graph.put(crawled, investor_id, document)
    await graph.put(crawled, "broken", {"name": "Broken", "error": "timeout", "crawled_at": 1})
    return graph


async def test_derive_counts_shared_companies_and_folds_same_named_investors():
    from batch.precompute_graph import GRAPH, derive

    graph = await crawled_graph()
    july_2026 = 1_782_000_000.0
    counts = await derive(graph, clock=lambda: july_2026)
    assert counts == {"investors": 3, "with_co_investors": 2}
    assert await graph.ids(GRAPH) == ["A", "B", "C"]  # the failed crawl is left out

    alpha = (await graph.get(GRAPH, "A"))["co_investors"]
    # Beta shares c1, c9 and (through the same-named "ALPHA Oy" in r3) c3; Outsider shares c2.
    assert [(p["investor"]["name"], p["count"]) for p in alpha] == [("Beta", 3), ("Outsider", 1)]
    beta = (await graph.get(GRAPH, "B"))["co_investors"]
    assert [(p["investor"]["id"], p["count"]) for p in beta] == [("A", 3)]
    assert (await graph.get(GRAPH, "C"))["co_investors"] == []


async def test_derive_summarises_each_investors_activity():
    from batch.precompute_graph import ACTIVITY, derive

    graph = await crawled_graph()
    await derive(graph, clock=lambda: 1_782_000_000.0)  # 2026-06-21
    alpha = await graph.get(ACTIVITY, "A")
    assert alpha["last_lead_date"] == "2026-04-14" and alpha["last_deal_date"] == "2026-09-01"
    assert alpha["leads_total"] == 1 and alpha["rounds_total"] == 3
    assert alpha["deals_last_12m"] == 2  # r1 and r3; r2 is from 2023
    assert alpha["rounds_by_stage"] == {"Seed": 2, "Series A": 1}
    assert alpha["companies_total"] == 4

    gamma = await graph.get(ACTIVITY, "C")
    assert gamma["last_lead_date"] is None and gamma["rounds_total"] == 0
    assert gamma["deals_last_12m"] == 0 and gamma["companies_total"] == 1


async def test_store_co_investors_reads_the_derived_graph(store):
    from batch.precompute_graph import derive

    graph = MemoryGraph()
    await crawl(store, graph, seeds=["Kelluu"], countries=[], clock=Clock())
    await derive(graph)

    reader = CalaDataStore(RecordedCala(), graph=graph)
    partners = await reader.co_investors(TESI)
    assert partners and all(isinstance(r, EntityRef) and count >= 1 for r, count in partners)
    assert [count for _, count in partners] == sorted((c for _, c in partners), reverse=True)
    assert NATO in {r.id for r, _ in partners}  # both are in Kelluu's Series A
    assert await reader.co_investors("00000000-0000-0000-0000-000000000000") == []


async def test_store_co_investors_survives_a_broken_graph():
    class Broken:
        async def get(self, collection, doc_id):
            raise ConnectionError("mongo down")

    assert await CalaDataStore(RecordedCala(), graph=Broken()).co_investors(TESI) == []


async def test_derive_handles_an_investor_with_no_companies_and_no_rounds():
    from batch.precompute_graph import ACTIVITY, GRAPH, derive
    from batch.precompute_graph import CRAWLED as crawled

    graph = await crawled_graph()
    empty = {
        "name": "Empty Fund",
        "investor": ref("E", "Empty Fund"),
        "portfolio": [],
        "rounds": [],
    }
    await graph.put(crawled, "E", empty)
    counts = await derive(graph, clock=lambda: 1_782_000_000.0)
    assert counts["investors"] == 4
    assert (await graph.get(GRAPH, "E"))["co_investors"] == []
    assert (await graph.get(ACTIVITY, "E"))["companies_total"] == 0


async def test_a_person_who_invests_is_crawled_like_any_investor(store, cala):
    person = {
        "id": "angel-1",
        "name": "Jane Angel",
        "entity_type": "Person",
        "description": "Angel investor.",
        "relationships": {
            "outgoing": {
                "INVESTED_IN": [
                    {"id": "c1", "name": "Acme", "entity_type": "Company", "properties": {}}
                ]
            }
        },
    }
    recorded = cala.entity

    async def entity(entity_id, **projection):
        return person if entity_id == "angel-1" else await recorded(entity_id, **projection)

    cala.entity = entity
    graph = MemoryGraph()
    ref = EntityRef(id="angel-1", name="Jane Angel", type="Person")
    assert await crawl_investor(store, graph, ref, now=1.0) == "crawled"
    stored = await graph.get(CRAWLED, "angel-1")
    assert stored["investor"]["type"] == "Person" and len(stored["portfolio"]) == 1
