"""CalaDataStore on recorded Cala responses (contracts/fixtures/raw/)."""

import pytest

from data.errors import NotFound
from data.store import CalaDataStore


@pytest.fixture
def store(cala):
    return CalaDataStore(cala)


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
