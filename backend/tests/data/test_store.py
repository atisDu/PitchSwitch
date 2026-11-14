"""CalaDataStore on recorded Cala responses (contracts/fixtures/raw/)."""

import pytest

from cache.graph import MemoryGraph
from data.errors import NotFound
from data.store import CalaDataStore
from tests.data.conftest import RecordedCala


@pytest.fixture
def store(cala):
    return CalaDataStore(cala, graph=MemoryGraph())


# --- resolve ----------------------------------------------------------------------------------


async def test_resolve_company_folds_the_two_kelluu_entries(store, cases):
    kelluu = cases["companies"]["kelluu"]
    refs = await store.resolve("Kelluu", "company")
    assert refs[0].id == kelluu["id"] and refs[0].name == "Kelluu Oy"
    assert refs[0].description
    assert kelluu["alt"][0] not in {ref.id for ref in refs}
    assert store.canonical(kelluu["alt"][0]) == kelluu["id"]
    assert all(ref.type in ("Company", "Organization") for ref in refs)


async def test_resolve_investor_keeps_the_richer_maki_entry_and_lists_its_funds(store, cases):
    maki = cases["investors"]["maki-vc"]
    refs = await store.resolve("Maki.vc", "investor")
    assert refs[0].id == maki["id"]
    assert maki["alt"][0] not in {ref.id for ref in refs}
    assert "MAKI.VC FUND I Ky" in {ref.name for ref in refs}


async def test_resolve_investor_prefers_the_fund_over_same_named_companies(store, cases):
    tesi = await store.resolve("Tesi", "investor")
    assert tesi[0].id == cases["investors"]["tesi"]["id"]
    assert store.canonical(tesi[0].id) == tesi[0].id  # the Italian TESIs are other firms
    assert len(tesi) > 1

    inventure = await store.resolve("Inventure", "investor")
    assert inventure[0].id == cases["investors"]["inventure"]["id"]


async def test_resolve_prefers_a_nordic_firm_among_equal_matches(store, cala, cases):
    finnish = cases["investors"]["inventure"]["id"]

    async def search(name, entity_types=None, limit=10):
        return {
            "entities": [
                {"id": "be-1", "name": "INVENTURE", "entity_type": "Company",
                 "description": "Belgian venture capital firm founded in 1980."},
                {"id": finnish, "name": "Inventure", "entity_type": "Organization",
                 "description": "a Finnish investment firm headquartered in Helsinki"},
                {"id": "se-1", "name": "Inventure Aktiebolag", "entity_type": "Company",
                 "description": "Swedish company headquartered in Stockholm."},
            ]
        }  # fmt: skip

    cala.search_entities = search
    refs = await store.resolve("Inventure", "investor")
    assert [ref.id for ref in refs] == [finnish, "be-1", "se-1"]
    assert store.canonical("be-1") == "be-1"  # a different firm: not folded into the Finnish one


async def test_resolve_lists_one_entry_per_firm(store):
    refs = await store.resolve("Sensofusion", "company")
    names = [ref.name for ref in refs]
    assert ("Sensofusion Oyj" in names) != ("Sensofusion Oy" in names)  # one of the two, not both
    assert "SENSOFUSION UK LTD" in names  # a different firm stays

    italian = [ref.name for ref in await store.resolve("Tesi", "investor")]
    assert "TESI S.P.A." in italian and "TESI FRANCE" in italian  # not merged into the fund


async def test_resolve_a_name_cala_does_not_know_gives_lookalikes_or_nothing(store, cala):
    lookalikes = await store.resolve("Nordic Air Defence", "company")
    assert lookalikes and lookalikes[0].name == "NORDIC AIR DEFENCE UK LTD"
    assert await store.resolve("No Such Firm Anywhere", "company") == []
    before = len(cala.calls)
    assert await store.resolve("   ", "company") == []
    assert len(cala.calls) == before


# --- company ----------------------------------------------------------------------------------


async def test_company_maps_a_startup(store, cases):
    company = await store.company(cases["companies"]["kelluu"]["id"])
    assert company.name == "Kelluu Oy" and company.type == "Company"
    assert company.stage == "Series A" and company.country == "Finland"
    assert company.total_funding_text == "€15.3M"
    assert company.industries == ["AEROSPACE_AND_DEFENSE"]
    assert company.description and company.sources
    assert {source.rank for source in company.sources} <= {
        "PRIMARY",
        "FILING",
        "PRESS",
        "AGGREGATOR",
        "UNKNOWN",
    }


async def test_company_works_for_an_investor(store, cases):
    tesi = await store.company(cases["investors"]["tesi"]["id"])
    assert tesi.name == "Tesi" and tesi.type == "Organization" and tesi.country == "Finland"


async def test_company_merges_the_other_entry_after_resolve(store, cases):
    sensofusion = cases["companies"]["sensofusion"]
    refs = await store.resolve("Sensofusion", "company")
    ids = {sensofusion["id"], *sensofusion["alt"]}
    assert refs[0].id in ids
    other = (ids - {refs[0].id}).pop()
    company = await store.company(other)  # asking by the other entry's ID
    assert company.id == refs[0].id
    assert company.country == "Finland" and company.description


async def test_company_fetches_each_entry_once_per_call(store, cala, cases):
    await store.company(cases["companies"]["stendr"]["id"])
    assert cala.calls == [("entity", cases["companies"]["stendr"]["id"])]


async def test_company_rejects_unknown_ids_and_other_entity_types(store, cases):
    with pytest.raises(NotFound):
        await store.company("00000000-0000-0000-0000-000000000000")
    with pytest.raises(NotFound):
        await store.company(cases["round_ids"][0])  # a funding round is not a company


# --- rounds ------------------------------------------------------------------------------------


async def test_rounds_of_kelluu_show_the_lead_and_the_sources(store, cases):
    kelluu = cases["companies"]["kelluu"]["id"]
    rounds = await store.rounds(kelluu)
    assert rounds[0].label == "Series A" and "Grant" in [r.label for r in rounds]
    series_a = rounds[0]
    assert series_a.date == "2026-04-14" and series_a.amount_eur == 15_000_000
    assert series_a.amount_text == "€15M" and series_a.sources
    leads = [i.investor.name for i in series_a.investors if i.is_lead]
    assert leads == ["NATO Innovation Fund"]
    assert [i.is_lead for i in series_a.investors].count(False) == 3
    assert all(r.company_id == kelluu for r in rounds)
    dated = [r.date for r in rounds if r.date]
    assert dated == sorted(dated, reverse=True)


async def test_backers_without_round_details_come_as_one_undated_round(store, cases):
    stendr = cases["companies"]["stendr"]["id"]
    (only,) = await store.rounds(stendr)
    assert only.id == f"{stendr}:backers" and only.company_id == stendr
    assert only.label is None and only.date is None and only.amount_eur is None
    assert len(only.investors) == 3 and all(i.is_lead is None for i in only.investors)
    assert only.sources


async def test_rounds_do_not_repeat_round_investors_as_backers(store, cases):
    kelluu = cases["companies"]["kelluu"]["id"]
    rounds = await store.rounds(kelluu)
    in_real_rounds = {
        i.investor.id for r in rounds if not r.id.endswith(":backers") for i in r.investors
    }
    for extra in (r for r in rounds if r.id.endswith(":backers")):
        assert not in_real_rounds & {i.investor.id for i in extra.investors}


async def test_an_investor_listed_under_two_ids_appears_once(store, cases):
    kelluu = cases["companies"]["kelluu"]
    await store.resolve("Kelluu", "company")  # joins the two Kelluu entries and their backers
    rounds = await store.rounds(kelluu["id"])
    names = [i.investor.name.lower() for r in rounds for i in r.investors]
    assert names.count("gungnir capital") == 1 and names.count("redstone") == 1
    backers = rounds[-1]
    assert backers.id.endswith(":backers")
    assert "gungnir capital" not in [i.investor.name.lower() for i in backers.investors]


async def test_rounds_are_empty_when_cala_has_none_or_the_id_is_unknown(store, cases):
    assert await store.rounds(cases["companies"]["sensofusion"]["id"]) == []
    assert await store.rounds("00000000-0000-0000-0000-000000000000") == []
    assert await store.investor_rounds("00000000-0000-0000-0000-000000000000") == []


async def test_investor_rounds_contain_the_investor_and_its_lead_flag(store, cases):
    maki = cases["investors"]["maki-vc"]["id"]
    rounds = await store.investor_rounds(maki)
    assert len(rounds) >= 5
    assert all(any(i.investor.id == maki for i in r.investors) for r in rounds)
    led = [r for r in rounds if any(i.investor.id == maki and i.is_lead for i in r.investors)]
    assert len(led) >= 2  # Aavuus and Metaktik pre-seeds
    dated = [r.date for r in rounds if r.date]
    assert dated == sorted(dated, reverse=True)


async def test_investor_rounds_use_the_main_id_after_resolve(store, cases):
    maki = cases["investors"]["maki-vc"]
    await store.resolve("Maki.vc", "investor")
    rounds = await store.investor_rounds(maki["alt"][0])  # asked by the other entry's ID
    assert rounds and all(any(i.investor.id == maki["id"] for i in r.investors) for r in rounds)
    assert not any(i.investor.id == maki["alt"][0] for r in rounds for i in r.investors)


# --- portfolio and people ----------------------------------------------------------------------


async def test_portfolio_lists_sourced_links_under_the_investor(store, cases):
    tesi = cases["investors"]["tesi"]["id"]
    portfolio = await store.portfolio(tesi)
    held = {link.company.id for link in portfolio}
    assert cases["companies"]["kelluu"]["id"] in held
    # Cala's graph has no Tesi -> NestAI link (only its text answers know that round).
    assert cases["companies"]["nestai"]["id"] not in held
    assert len(portfolio) >= 40 and len(held) == len(portfolio)
    assert all(link.investor_id == tesi for link in portfolio)
    assert sum(bool(link.sources) for link in portfolio) > len(portfolio) // 2
    names = [link.company.name.lower() for link in portfolio]
    assert names == sorted(names)


async def test_portfolio_joins_both_entries_of_a_firm_after_resolve(store, cases):
    maki = cases["investors"]["maki-vc"]
    alone = await store.portfolio(maki["id"])
    await store.resolve("Maki.vc", "investor")
    joined = await store.portfolio(maki["alt"][0])
    assert len(joined) > len(alone)
    assert all(link.investor_id == maki["id"] for link in joined)
    assert len({link.company.id for link in joined}) == len(joined)


async def test_people_of_a_company_carry_roles_and_sources(store, cases):
    kelluu = cases["companies"]["kelluu"]["id"]
    people = await store.people(kelluu)
    roles = [person.role for person in people]
    assert roles.count("BOARD") == 4 and "CEO" in roles and "FOUNDER" in roles
    assert "EMPLOYEE" in roles
    assert all(person.company_id == kelluu for person in people)
    assert all(person.person.type == "Person" for person in people)
    assert any(person.sources for person in people)


async def test_people_work_for_an_investor_id_too(store, cases):
    redstone = await store.people("a1f7d57d-39a4-486f-bd9b-39b8b50ab1ff")
    assert isinstance(redstone, list)
    tesi = await store.people(cases["investors"]["tesi"]["id"])
    assert tesi == [] or all(
        person.company_id == cases["investors"]["tesi"]["id"] for person in tesi
    )


async def test_portfolio_and_people_are_empty_for_unknown_ids(store):
    nobody = "00000000-0000-0000-0000-000000000000"
    assert await store.portfolio(nobody) == []
    assert await store.people(nobody) == []


# --- sourced_answer ----------------------------------------------------------------------------


async def test_sourced_answer_returns_markdown_and_claims_with_documents(store, cases):
    question = cases["questions"]["rounds-kelluu"]
    markdown, reasons = await store.sourced_answer(f"  {question} ")
    assert "NATO Innovation Fund" in markdown
    assert len(reasons) >= 3 and all(reason.text for reason in reasons)
    cited = [source for reason in reasons for source in reason.sources]
    assert cited and all(source.name for source in cited)
    assert any((source.url or "").startswith("http") for source in cited)


async def test_sourced_answer_for_nothing(store, cala):
    assert await store.sourced_answer("   ") == ("", [])
    assert cala.calls == []
    assert await store.sourced_answer("A question Cala has no answer for") == ("", [])


# --- candidate_competitors ---------------------------------------------------------------------

PEERS = "List companies that develop products similar to those of"


def peers_answer(*rows_and_entities):
    """A canned answer to the peers query: (name, country, entity or None) per row."""
    return {
        "results": [
            {"name": name, "country": country, "description": f"{name} builds counter-drone kit"}
            for name, country, _ in rows_and_entities
        ],
        "entities": [entity for _, _, entity in rows_and_entities if entity],
    }


def with_peers(cala, answer):
    """Make the recorded Cala answer the peers query with `answer`."""
    recorded = cala.query

    async def query(text):
        if text.startswith(PEERS):
            cala.calls.append(("query", text))
            return answer
        return await recorded(text)

    cala.query = query


async def test_candidates_ask_for_peers_and_for_the_industry_in_each_country(store, cala, cases):
    kelluu = await store.company(cases["companies"]["kelluu"]["id"])
    cala.calls.clear()
    candidates = await store.candidate_competitors(kelluu)

    queries = [text for kind, text in cala.calls if kind == "query"]
    assert len(queries) == 8 and queries[0].startswith(f"{PEERS} Kelluu (")
    by_country = queries[1:]
    assert all(
        q.startswith("companies.industry=AEROSPACE_AND_DEFENSE.country=") for q in by_country
    )
    assert by_country[0] == cases["queries"]["candidates-finland"]  # the recorded query, verbatim

    names = [c.name for c in candidates]
    assert {"Aavuus", "Kova Labs", "Metaktik", "ReOrbit", "Heart Aerospace"} <= set(names)
    assert kelluu.id not in {c.id for c in candidates} and "Kelluu Oy" not in names
    assert len({c.id for c in candidates}) == len(candidates)
    countries = [c.country for c in candidates]
    assert countries[: countries.count("Finland")] == ["Finland"] * countries.count("Finland")
    assert all(c.description for c in candidates)
    # Series A like Kelluu, so ahead of a pre-seed company from the same country
    assert names.index("ReOrbit") < names.index("Metaktik")


async def test_stendr_is_searched_as_defence_not_as_software(store, cala, cases):
    stendr = await store.company(cases["companies"]["stendr"]["id"])
    assert stendr.industries[0] == "SOFTWARE_AND_SERVICES"  # Cala lists the broad tag first
    cala.calls.clear()
    candidates = await store.candidate_competitors(stendr)
    queries = [text for kind, text in cala.calls if kind == "query"]
    assert not any("SOFTWARE_AND_SERVICES" in q for q in queries)
    assert sum("industry=AEROSPACE_AND_DEFENSE" in q for q in queries) == 7
    assert ".country=Norway." in queries[1]  # Stendr's own country first
    assert "drone defence" in queries[0]  # its description says what it does: used as a hint
    assert candidates and "Stendr" not in [c.name for c in candidates]


async def test_sensofusion_without_any_tag_still_finds_stendr(store, cala, cases):
    refs = await store.resolve("Sensofusion", "company")
    sensofusion = await store.company(refs[0].id)
    assert sensofusion.industries == []
    assert "defense technology" in sensofusion.description  # not the registry boilerplate
    cala.calls.clear()
    candidates = await store.candidate_competitors(sensofusion)
    queries = [text for kind, text in cala.calls if kind == "query"]
    # no description hint (it is thin), and the industry is read from the description
    assert queries[0].startswith(f"{PEERS} Sensofusion and compete with it")
    assert sum("industry=AEROSPACE_AND_DEFENSE" in q for q in queries) == 7
    assert "Stendr" in [c.name for c in candidates]
    assert not any("sensofusion" in c.name.lower() for c in candidates)


async def test_peers_come_first_and_unlinked_rows_are_looked_up_by_name(store, cala, cases):
    stendr_id = cases["companies"]["stendr"]["id"]
    sensofusion = await store.company(cases["companies"]["sensofusion"]["id"])
    with_peers(
        cala,
        peers_answer(
            ("Sensofusion", "Finland", None),  # the company itself
            ("MyDefence", "Denmark", {"id": "my-1", "name": "MYDEFENCE GROUP APS",
                                      "entity_type": "Company", "mentions": ["MyDefence"]}),
            ("Nordic Air Defence (NAD)", "Sweden", None),  # Cala only has a UK shell by that name
            ("Kelluu", "Finland", None),  # no entity here, but the Finland list has one
            ("NestAI", "Finland", None),  # in no other answer: found by name search
            ("Stendr", "Norway", {"id": stendr_id, "name": "Stendr", "entity_type": "Company"}),
        ),
    )  # fmt: skip
    cala.calls.clear()
    candidates = await store.candidate_competitors(sensofusion)

    names = [c.name for c in candidates]
    # peers first, in Cala's order
    assert names[:4] == ["MYDEFENCE GROUP APS", "Kelluu Oy", "NestAI", "Stendr"]
    assert names.count("Stendr") == 1  # also in the Norway list: not repeated
    assert not any("NORDIC AIR DEFENCE" in name.upper() for name in names)
    assert candidates[0].country == "Denmark" and "counter-drone" in candidates[0].description
    searched = [name for kind, name in cala.calls if kind == "search_entities"]
    assert searched == ["Nordic Air Defence", "NestAI"]
    assert "Aavuus" in names[4:]  # the industry lists follow


async def test_candidates_respect_k_and_survive_a_failing_country(store, cala, cases):
    kelluu = await store.company(cases["companies"]["kelluu"]["id"])
    assert len(await store.candidate_competitors(kelluu, k=2)) == 2
    assert await store.candidate_competitors(kelluu, k=0) == []

    real_query = cala.query

    async def flaky(text):
        if ".country=Sweden." in text or text.startswith(PEERS):
            raise RuntimeError("Cala timed out")
        return await real_query(text)

    cala.query = flaky
    names = {c.name for c in await store.candidate_competitors(kelluu)}
    assert "Aavuus" in names and "Heart Aerospace" not in names


async def test_candidates_fail_loudly_when_every_query_fails(store, cala, cases):
    kelluu = await store.company(cases["companies"]["kelluu"]["id"])

    async def down(text):
        raise RuntimeError("Cala is down")

    cala.query = down
    with pytest.raises(RuntimeError):
        await store.candidate_competitors(kelluu)


def test_primary_industry_and_peers_query_text():
    from contracts.schemas import Company
    from data.store import industry_queries, peers_query, primary_industry

    def company(name, description=None, industries=()):
        return Company(
            id="x", name=name, type="Company", description=description, industries=list(industries)
        )

    broad_first = ["SOFTWARE_AND_SERVICES", "AEROSPACE_AND_DEFENSE", "HARDWARE_AND_EQUIPMENT"]
    assert primary_industry(company("Stendr", "Drone defence platform", broad_first)) == (
        "AEROSPACE_AND_DEFENSE"
    )
    assert primary_industry(company("Acme", "Dental booking app", broad_first)) == (
        "AEROSPACE_AND_DEFENSE"  # the only narrow tag
    )
    assert primary_industry(company("Acme", "CRM", ["SOFTWARE_AND_SERVICES"])) == (
        "SOFTWARE_AND_SERVICES"
    )
    assert primary_industry(company("Sensofusion Oy", "Finnish defense technology company")) == (
        "AEROSPACE_AND_DEFENSE"
    )
    assert primary_industry(company("Mystery Oy", "Finnish company founded in 2016")) is None
    assert industry_queries(company("Mystery Oy")) == []

    thin = company(
        "Sensofusion Oyj", "Finnish company founded in 2016 and headquartered in Vantaa."
    )
    assert peers_query(thin).startswith(f"{PEERS} Sensofusion and compete with it, in Finland,")
    rich = company("Stendr", "Norwegian defence technology company developing AI-native sensors.")
    assert f"{PEERS} Stendr (Norwegian defence technology company developing" in peers_query(rich)
    assert peers_query(rich).endswith(
        "Return name, description, country, funding_stage, total_funding."
    )


# --- one firm, one name, across processes -------------------------------------------------------


async def test_a_second_process_knows_which_entries_are_one_firm(cala, cases):
    sensofusion = cases["companies"]["sensofusion"]
    shared = MemoryGraph()  # stands in for the shared Atlas database
    first = CalaDataStore(cala, graph=shared)
    main = (await first.resolve("Sensofusion", "company"))[0]
    other = ({sensofusion["id"], *sensofusion["alt"]} - {main.id}).pop()
    assert await shared.ids("entity_aliases") == [other]

    second = CalaDataStore(RecordedCala(), graph=shared)  # a fresh process: nothing resolved
    company = await second.company(other)
    assert company.id == main.id and "defense technology" in company.description
    assert second.canonical(other) == main.id


async def test_a_competitor_is_shown_under_its_main_name(cala, cases):
    sensofusion = cases["companies"]["sensofusion"]
    shared = MemoryGraph()
    main = (await CalaDataStore(cala, graph=shared).resolve("Sensofusion", "company"))[0]
    other = ({sensofusion["id"], *sensofusion["alt"]} - {main.id}).pop()

    fresh = RecordedCala()
    store = CalaDataStore(fresh, graph=shared)
    stendr = await store.company(cases["companies"]["stendr"]["id"])
    with_peers(  # Cala names the rival by its other entry, as it does live
        fresh,
        peers_answer(
            ("Sensofusion", "Finland", {"id": other, "name": "Sensofusion Other Entry",
                                        "entity_type": "Company", "mentions": ["Sensofusion"]}),
        ),
    )  # fmt: skip
    first = (await store.candidate_competitors(stendr))[0]
    assert first.id == main.id and first.name == main.name


async def test_investor_duplicates_found_in_rounds_are_shared_too(cala, cases):
    kelluu = cases["companies"]["kelluu"]
    shared = MemoryGraph()
    first = CalaDataStore(cala, graph=shared)
    await first.resolve("Kelluu", "company")
    await first.rounds(kelluu["id"])  # finds Gungnir Capital and Redstone under two IDs each
    saved = await shared.ids("entity_aliases")
    assert kelluu["alt"][0] in saved and len(saved) >= 3

    second = CalaDataStore(RecordedCala(), graph=shared)
    rounds = await second.rounds(kelluu["alt"][0])  # no resolve in this process
    names = [i.investor.name.lower() for r in rounds for i in r.investors]
    assert names.count("gungnir capital") == 1 and names.count("redstone") == 1
    assert all(r.company_id == kelluu["id"] for r in rounds)


async def test_the_store_works_when_the_shared_graph_is_down(cala, cases):
    class Down:
        async def ids(self, collection):
            raise ConnectionError("mongo down")

        async def get(self, collection, doc_id):
            raise ConnectionError("mongo down")

        async def put(self, collection, doc_id, document):
            raise ConnectionError("mongo down")

    store = CalaDataStore(cala, graph=Down())
    refs = await store.resolve("Kelluu", "company")
    assert refs[0].id == cases["companies"]["kelluu"]["id"]
    assert store.canonical(cases["companies"]["kelluu"]["alt"][0]) == refs[0].id  # in this process
    assert (await store.company(refs[0].id)).name == "Kelluu Oy"
    assert await store.co_investors(refs[0].id) == []


# --- vector search (A13, behind USE_VECTOR_SEARCH) ------------------------------------------------


class TopicEmbedder:
    """Embeds by counting topic words, so tests need no Gemini."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts):
        self.calls += 1
        topics = ("drone", "airship", "satellite", "dental")
        return [[float(t.lower().count(topic)) + 0.01 for topic in topics] for t in texts]


async def test_vector_search_is_off_by_default(store, cases, monkeypatch):
    monkeypatch.delenv("USE_VECTOR_SEARCH", raising=False)
    kelluu = await store.company(cases["companies"]["kelluu"]["id"])
    await store.candidate_competitors(kelluu)
    assert store._vectors is None  # never opened: no embeddings, no extra queries


async def test_vector_search_adds_similar_companies_seen_elsewhere(cala, cases, monkeypatch):
    from cache.vector import VectorStore
    from contracts.schemas import Company

    monkeypatch.setenv("USE_VECTOR_SEARCH", "true")
    graph = MemoryGraph()
    embedder = TopicEmbedder()
    # A company met while analysing some other space; no Cala query for Kelluu returns it.
    rival = Company(
        id="rival-1", name="SkyWhale", type="Company", description="Cargo airship maker"
    )
    other = Company(id="other-1", name="Toothly", type="Company", description="Dental booking app")
    await VectorStore(graph=graph, embedder=embedder).upsert([rival, other])

    store = CalaDataStore(cala, graph=graph)
    store._vectors = VectorStore(graph=graph, embedder=embedder)
    kelluu = await store.company(cases["companies"]["kelluu"]["id"])
    before = [c.id for c in await CalaDataStore(RecordedCala(), graph=MemoryGraph())
              .candidate_competitors(kelluu)]  # fmt: skip
    after = await store.candidate_competitors(kelluu)

    names = [c.name for c in after]
    assert "SkyWhale" in names and "rival-1" not in before
    assert names.index("SkyWhale") < names.index("Aavuus")  # ahead of the industry lists
    assert set(before) <= {c.id for c in after}  # nothing that was there is lost
    assert kelluu.id not in {c.id for c in after}
    assert len({c.id for c in after}) == len(after)
    # every candidate is now stored, so the next search embeds nothing
    calls = embedder.calls
    await store.candidate_competitors(kelluu)
    assert embedder.calls == calls


async def test_a_failing_embedder_leaves_the_candidates_as_they_were(cala, cases, monkeypatch):
    from cache.vector import VectorStore

    class Broken:
        async def embed(self, texts):
            raise RuntimeError("Gemini is down")

    monkeypatch.setenv("USE_VECTOR_SEARCH", "true")
    store = CalaDataStore(cala, graph=MemoryGraph())
    store._vectors = VectorStore(graph=MemoryGraph(), embedder=Broken())
    kelluu = await store.company(cases["companies"]["kelluu"]["id"])
    with_broken = [c.id for c in await store.candidate_competitors(kelluu)]
    monkeypatch.setenv("USE_VECTOR_SEARCH", "false")
    assert with_broken == [c.id for c in await store.candidate_competitors(kelluu)]
