"""FakeDataStore and the committed fixtures in contracts/fixtures/models/."""

import json
import re

import pytest
from pydantic import TypeAdapter

import data
from contracts.schemas import (
    CONTRACT_VERSION,
    AgentEvent,
    Brief,
    Company,
    EntityRef,
    FounderReport,
    InvestorCheck,
    PersonLink,
    PortfolioLink,
    Reason,
    Round,
)
from data.build_fixtures import build
from data.config import MODELS_DIR, RAW_DIR
from data.errors import NotFound
from data.fake_store import FakeDataStore

INDEX = json.loads((MODELS_DIR / "index.json").read_text())
COMPANIES = {key: case for key, case in INDEX["companies"].items() if case["id"]}
INVESTORS = INDEX["investors"]

# File-name prefix -> the model each fixture file must validate against.
SHAPES = {
    "resolve_": TypeAdapter(list[EntityRef]),
    "company_": TypeAdapter(Company),
    "rounds_": TypeAdapter(list[Round]),
    "investor_rounds_": TypeAdapter(list[Round]),
    "portfolio_": TypeAdapter(list[PortfolioLink]),
    "people_": TypeAdapter(list[PersonLink]),
    "candidates_": TypeAdapter(list[Company]),
    "co_investors_": TypeAdapter(list[tuple[EntityRef, int]]),
    "founder_report_": TypeAdapter(FounderReport),
    "investor_check_": TypeAdapter(InvestorCheck),
    "brief_": TypeAdapter(Brief),
    "agent_events_": TypeAdapter(list[AgentEvent]),
}


@pytest.fixture
def store():
    return FakeDataStore()


def load(name):
    return json.loads((MODELS_DIR / name).read_text())


def test_index_matches_the_contract_and_the_folder():
    assert INDEX["contract_version"] == CONTRACT_VERSION
    on_disk = sorted(p.name for p in MODELS_DIR.glob("*.json") if p.name != "index.json")
    assert INDEX["files"] == on_disk


def test_every_fixture_file_is_a_valid_contract_model():
    for name in INDEX["files"]:
        if name.startswith("sourced_answer_"):
            answer = load(name)
            assert answer["question"] and isinstance(answer["markdown"], str)
            TypeAdapter(list[Reason]).validate_python(answer["reasons"])
            continue
        prefix = next(p for p in sorted(SHAPES, key=len, reverse=True) if name.startswith(p))
        SHAPES[prefix].validate_python(load(name))


def test_fixtures_are_rebuilt_from_raw_without_changes(tmp_path):
    build(RAW_DIR, tmp_path)
    for name in [*INDEX["files"], "index.json"]:
        assert (tmp_path / name).read_text() == (MODELS_DIR / name).read_text(), name


async def test_resolve_puts_the_demo_entity_first(store):
    for case in COMPANIES.values():
        refs = await store.resolve(case["name"], "company")
        assert refs and refs[0].id == case["id"], case["name"]
    for case in INVESTORS.values():
        refs = await store.resolve(case["name"], "investor")
        assert refs and refs[0].id == case["id"], case["name"]


async def test_resolve_falls_back_to_a_name_match_and_to_nothing(store):
    name = COMPANIES["kelluu"]["name"]
    assert (await store.resolve(name.upper()[:5], "company"))[0].id == COMPANIES["kelluu"]["id"]
    assert await store.resolve("zzz no such firm", "investor") == []
    assert await store.resolve("", "company") == []


async def test_company_works_for_companies_investors_and_aliases(store):
    for case in [*COMPANIES.values(), *INVESTORS.values()]:
        company = await store.company(case["id"])
        assert company.id == case["id"] and company.name
        for alt in case["alt_ids"]:
            assert (await store.company(alt)).id == case["id"]
    with pytest.raises(NotFound):
        await store.company("00000000-0000-0000-0000-000000000000")


async def test_kelluu_series_a_is_led_by_nato_innovation_fund(store):
    rounds = await store.rounds(COMPANIES["kelluu"]["id"])
    series_a = next(r for r in rounds if r.label == "Series A")
    leads = [i.investor.id for i in series_a.investors if i.is_lead]
    assert leads == [INVESTORS["nato-innovation-fund"]["id"]]
    assert series_a.sources and series_a.amount_eur == 15_000_000
    assert all(r.company_id == COMPANIES["kelluu"]["id"] for r in rounds)


async def test_investor_methods_return_sourced_models(store):
    tesi = INVESTORS["tesi"]["id"]
    portfolio = await store.portfolio(tesi)
    assert COMPANIES["kelluu"]["id"] in {link.company.id for link in portfolio}
    assert all(link.investor_id == tesi for link in portfolio)
    assert any(link.sources for link in portfolio)

    rounds = await store.investor_rounds(tesi)
    assert rounds and all(any(i.investor.id == tesi for i in r.investors) for r in rounds)

    partners = await store.co_investors(tesi)
    assert partners and all(isinstance(ref, EntityRef) and count >= 1 for ref, count in partners)
    assert [count for _, count in partners] == sorted((c for _, c in partners), reverse=True)


async def test_people_work_for_a_company(store):
    people = await store.people(COMPANIES["kelluu"]["id"])
    assert {"BOARD", "CEO", "FOUNDER"} <= {p.role for p in people}
    assert all(p.company_id == COMPANIES["kelluu"]["id"] for p in people)


async def test_candidates_exclude_the_company_and_respect_k(store):
    for case in COMPANIES.values():
        company = await store.company(case["id"])
        candidates = await store.candidate_competitors(company)
        assert candidates and case["id"] not in {c.id for c in candidates}
        assert len({c.id for c in candidates}) == len(candidates)
        assert len(await store.candidate_competitors(company, k=2)) == 2


async def test_unknown_ids_give_empty_lists(store):
    nobody = "00000000-0000-0000-0000-000000000000"
    assert await store.rounds(nobody) == []
    assert await store.investor_rounds(nobody) == []
    assert await store.portfolio(nobody) == []
    assert await store.people(nobody) == []
    assert await store.co_investors(nobody) == []
    ghost = Company(id=nobody, name="Ghost", type="Company")
    assert await store.candidate_competitors(ghost) == []


async def test_sourced_answer_matches_a_reworded_question(store):
    markdown, reasons = await store.sourced_answer("Who led Kelluu's funding rounds?")
    assert "Kelluu" in markdown
    assert reasons and any(reason.sources for reason in reasons)
    assert await store.sourced_answer("What is the weather in Lisbon?") == ("", [])


def test_get_store_returns_the_fake_store_by_default(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    data.get_store.cache_clear()
    try:
        assert isinstance(data.get_store(), FakeDataStore)
    finally:
        data.get_store.cache_clear()


# --- Sample API responses (placeholders until B's API) ------------------------------------------


def test_founder_reports_follow_the_contract_rules():
    assert INDEX["founder_mode"]
    for entry in INDEX["founder_mode"]:
        report = FounderReport.model_validate(load(entry["file"]))
        assert report.company.id == entry["company_id"]
        assert report.competitors and report.company.id not in {
            c.company.id for c in report.competitors
        }
        assert report.pitch or report.skip
        assert all(not score.conflicts for score in report.pitch)
        assert all(score.conflicts for score in report.skip)
        for scores in (report.pitch, report.skip):
            values = [score.score for score in scores]
            assert values == sorted(values, reverse=True)
            assert all(0 <= value <= 100 for value in values)
            assert all(score.reasons for score in scores)


def test_investor_checks_cover_the_startup_and_its_competitors():
    assert INDEX["investor_mode"]
    for entry in INDEX["investor_mode"]:
        check = InvestorCheck.model_validate(load(entry["file"]))
        assert check.investor.id == entry["investor_id"]
        assert check.company.id == entry["company_id"]
        allowed = {check.company.id} | {c.company.id for c in check.competitors}
        assert {r.company_id for r in check.rounds} <= allowed


def test_brief_markers_point_into_the_citations():
    assert INDEX["briefs"]
    for entry in INDEX["briefs"]:
        brief = Brief.model_validate(load(entry["file"]))
        numbers = [int(n) for n in re.findall(r"\[(\d+)\]", brief.markdown)]
        assert numbers, entry["file"]
        assert min(numbers) == 1 and max(numbers) == len(brief.citations)


def test_event_streams_end_with_done():
    slush = TypeAdapter(list[AgentEvent]).validate_python(load("agent_events_slush_prep.json"))
    assert slush[-1].type == "done"
    assert any(e.type == "brief" and e.brief and e.investor and e.investor_name for e in slush)
    assert any(e.type == "error" and e.investor_name for e in slush)

    chat = TypeAdapter(list[AgentEvent]).validate_python(load("agent_events_chat.json"))
    assert chat[-1].type == "done" and chat[-1].citations
    text = "".join(e.message for e in chat if e.type == "text")
    numbers = [int(n) for n in re.findall(r"\[(\d+)\]", text)]
    assert numbers and max(numbers) == len(chat[-1].citations)
