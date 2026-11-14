"""The MCP server in-process, on the fake store with a fixed judgement."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import core.competitors as competitors
from cache.graph import MemoryGraph
from contracts.schemas import Competitor, Conflict, EntityRef
from core.competitors import Judgement
from data import get_store
from mcp_server.server import server

STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"


@pytest.fixture(autouse=True)
def judged(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()

    async def fake_judge(company, graph):
        direct = [Competitor(company=await get_store().company(KELLUU), reason="both fly")]
        return Judgement(direct=direct, space=[])

    monkeypatch.setattr(competitors, "cached_judge", fake_judge)
    monkeypatch.setattr(competitors, "_graph", MemoryGraph())
    monkeypatch.setattr(competitors, "_memo", {})
    yield
    get_store.cache_clear()


async def test_lists_the_contract_tools_with_schemas():
    listed = {t.name: t for t in await server.list_tools()}
    assert list(listed) == [
        "resolve_company", "find_competitors", "get_rounds", "investor_profile",
        "check_conflict", "rank_investors", "investor_brief",
    ]  # contracts/api.md, MCP tools
    assert listed["check_conflict"].input_schema["required"] == ["investor_id", "company_id"]
    assert all(t.description for t in listed.values())


async def test_should_i_pitch_this_fund():
    found = await server.call_tool("resolve_company", {"name": "Stendr"})
    refs = [EntityRef.model_validate(r) for r in found.structured_content["result"]]
    assert STENDR in [r.id for r in refs]
    result = await server.call_tool("check_conflict", {"investor_id": NIF, "company_id": STENDR})
    conflicts = [Conflict.model_validate(c) for c in result.structured_content["result"]]
    assert [c.competitor.id for c in conflicts] == [KELLUU] and conflicts[0].sources


async def test_unknown_id_is_told_in_words():
    with pytest.raises(ToolError, match="no fixture for company or investor nope"):
        await server.call_tool("check_conflict", {"investor_id": "nope", "company_id": STENDR})
