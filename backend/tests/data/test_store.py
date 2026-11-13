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
