"""The MCP server in-process, on the fake store with a fixed judgement."""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

import core.competitors as competitors
import mcp_server.server as mcp
from cache.graph import MemoryGraph
from contracts.schemas import Competitor, Conflict, EntityRef
from core.competitors import Judgement
from data import NotFound, get_store
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
    unknown = "00000000-0000-4000-8000-000000000000"
    with pytest.raises(ToolError, match=f"no fixture for company or investor {unknown}"):
        await server.call_tool("check_conflict", {"investor_id": unknown, "company_id": STENDR})
    with pytest.raises(ToolError, match="No company or investor with that ID.*resolve_company"):
        await server.call_tool("check_conflict", {"investor_id": "Maki.vc", "company_id": STENDR})


async def test_slow_call_says_call_again_and_the_retry_gets_the_same_work(monkeypatch):
    runs, ready = [], asyncio.Event()

    async def slow_brief(investor_id: str) -> str:
        runs.append(investor_id)
        await ready.wait()
        return f"brief on {investor_id}"

    monkeypatch.setattr(mcp, "REPLY_WITHIN", 0.01)
    tool = mcp._told(slow_brief)
    with pytest.raises(ToolError, match="Still working.*Call slow_brief again"):
        await tool(investor_id=STENDR)
    ready.set()
    assert await tool(investor_id=STENDR) == f"brief on {STENDR}"  # joins the work under way
    await asyncio.sleep(0)
    assert runs == [STENDR] and not mcp._running  # ran once; forgotten when done


async def test_failure_after_the_deadline_is_told_on_the_retry(monkeypatch):
    ready = asyncio.Event()

    async def slow_failure(company_id: str) -> str:
        await ready.wait()
        raise NotFound("no entity with this ID")

    monkeypatch.setattr(mcp, "REPLY_WITHIN", 0.01)
    tool = mcp._told(slow_failure)
    with pytest.raises(ToolError, match="Still working"):
        await tool(company_id=STENDR)
    ready.set()
    with pytest.raises(ToolError, match="no entity with this ID"):
        await tool(company_id=STENDR)


def test_http_needs_the_token_in_a_header_or_in_the_url():
    token = "t" * 24
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"}}}
    accept = {"accept": "application/json, text/event-stream"}
    app = mcp.TokenGate(server.streamable_http_app(host="0.0.0.0"), token)
    with TestClient(app, base_url="https://demo.example") as client:
        for path, extra in [
            ("/mcp", {}),
            ("/mcp", {"authorization": "Bearer wrong"}),
            ("/mcp?key=wrong", {}),
            ("/mcp?key=", {}),
        ]:
            refused = client.post(path, json=init, headers=accept | extra)
            assert refused.status_code == 401 and "token" in refused.json()["error"]
        for path, extra in [
            ("/mcp", {"authorization": f"Bearer {token}"}),
            ("/mcp", {"authorization": f"bearer {token}"}),
            (f"/mcp?key={token}", {}),
        ]:
            ok = client.post(path, json=init, headers=accept | extra)
            assert ok.status_code == 200 and '"pitchswitch"' in ok.text


def test_http_refuses_to_start_without_a_real_token(monkeypatch):
    for bad in ("", "short"):
        monkeypatch.setenv("MCP_TOKEN", bad)
        with pytest.raises(SystemExit, match="MCP_TOKEN must be set"):
            mcp._token()


def test_setup_text_has_a_ready_line_per_client():
    text = mcp.setup("https://demo.example/", "t" * 24)
    assert "https://demo.example/mcp?key=" + "t" * 24 in text
    assert 'claude mcp add --transport http pitchswitch https://demo.example/mcp --header' in text
    assert '"Authorization": "Bearer ' + "t" * 24 in text
