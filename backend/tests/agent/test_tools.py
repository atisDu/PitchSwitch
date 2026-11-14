"""agent/tools.py on the fake store, with a fixed judgement instead of Gemini."""

import pytest

import core.competitors as competitors
from agent import tools
from contracts.schemas import Competitor, FounderReport
from core.competitors import Judgement
from data import get_store

STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"


@pytest.fixture(autouse=True)
def judged(monkeypatch):
    """Stendr's one direct competitor is Kelluu; the other candidates are its market space."""
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()

    async def fake_judge(company, graph):
        store = get_store()
        direct = [Competitor(company=await store.company(KELLUU), reason="both fly")]
        space = [c for c in await store.candidate_competitors(company) if c.id != KELLUU]
        return Judgement(direct=direct, space=space)

    monkeypatch.setattr(competitors, "cached_judge", fake_judge)
    monkeypatch.setattr(competitors, "_graph", object())
    monkeypatch.setattr(competitors, "_memo", {})
    yield
    get_store.cache_clear()


def test_declarations_come_from_signatures():
    for fn in [*tools.MCP_TOOLS, tools.sourced_answer]:
        d = tools.declaration(fn)
        assert d.name == fn.__name__ and d.description
        assert d.parameters_json_schema["required"]
    schema = tools.declaration(tools.resolve_company).parameters_json_schema
    assert schema["properties"]["kind"]["enum"] == ["company", "investor"]


async def facts_of(tool, **args):
    result = await getattr(tools, tool)(**args)
    names = tools.names_in(result)
    for key, value in args.items():  # the agent only passes IDs it has seen: it has their names
        if key.endswith("_id") and value not in names:
            names[value] = (await get_store().company(value)).name
    return result, tools.facts(tool, args, result, names)


async def test_conflict_facts_carry_sources_and_no_conflict_is_said():
    _, hit = await facts_of("check_conflict", investor_id=NIF, company_id=STENDR)
    assert hit[0].text.startswith("Conflict: NATO Innovation Fund backs Kelluu")
    assert hit[0].sources and len(hit[0].sources) <= 3
    _, clear = await facts_of("check_conflict", investor_id=MAKI, company_id=STENDR)
    assert [f.text[:18] for f in clear] == ["No conflict found:"] and not clear[0].sources


async def test_rank_investors_is_cut_and_becomes_facts():
    report, facts = await facts_of("rank_investors", company_id=STENDR, limit=2)
    assert isinstance(report, FounderReport) and len(report.pitch) == 2
    texts = [f.text for f in facts]
    assert texts[0].startswith("Kelluu Oy is a direct competitor of Stendr")
    assert any(t.startswith("Conflict: NATO Innovation Fund backs Kelluu") for t in texts)
    assert sum("on the Pitch list" in t for t in texts) == 2


async def test_rounds_and_profile_name_their_companies():
    _, rounds = await facts_of("get_rounds", company_id=KELLUU)
    assert rounds and all(f.text.startswith("Kelluu") and f.sources for f in rounds)
    assert any("NATO Innovation Fund (lead)" in f.text for f in rounds)
    profile, facts = await facts_of("investor_profile", investor_id=MAKI)
    assert set(profile.companies) == {rd.company_id for rd in profile.rounds}
    assert facts[0].text.startswith("Maki.vc: ")
    assert not any(f.text.startswith("a company") for f in facts)
