import json

import pytest
from fastapi.testclient import TestClient

import api.main as api
import core.briefs as briefs
from agent.llm import LLMError
from api.main import app
from cache.graph import MemoryGraph
from contracts.schemas import (
    CONTRACT_VERSION,
    AgentEvent,
    Brief,
    Competitor,
    FounderReport,
    InvestorCheck,
)
from core.competitors import Judgement
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
SENSOFUSION_ALIAS = "5c699806-0fea-4e62-a594-717d4d85516c"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"
STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
SENSOFUSION = "202e9283-6455-486f-8868-03c7e0d0cf29"
NESTAI = "14359613-a45f-4804-892d-3b9dd9e927a9"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"
RIVALS = {STENDR: [KELLUU, SENSOFUSION], SENSOFUSION: [STENDR, KELLUU]}


@pytest.fixture
def judged(monkeypatch):
    """Fake Gemini judge: fixed rivals per company; records which companies it was asked about."""
    calls = []

    async def fake_judge(company, graph):
        calls.append(company.id)
        store = get_store()
        ids = RIVALS.get(company.id, [])
        direct = [Competitor(company=await store.company(i), reason=f"judged {i}") for i in ids]
        space = [c for c in await store.candidate_competitors(company) if c.id not in ids]
        return Judgement(direct=direct, space=space)

    monkeypatch.setattr(api, "cached_judge", fake_judge)
    monkeypatch.setattr(api, "_graph", MemoryGraph())
    monkeypatch.setattr(api, "_judgements", {})
    return calls


@pytest.fixture
def client(monkeypatch, judged):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield TestClient(app)
    get_store.cache_clear()


def events(resp) -> list[AgentEvent]:
    assert resp.headers["content-type"].startswith("text/event-stream")
    chunks = [c for c in resp.text.split("\n\n") if c]
    assert all(c.startswith("data: ") for c in chunks)
    return [AgentEvent.model_validate(json.loads(c[6:])) for c in chunks]


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True, "contract_version": CONTRACT_VERSION}


def test_resolve(client):
    refs = client.post("/api/resolve", json={"name": "Kelluu", "kind": "company"}).json()
    assert KELLUU in [r["id"] for r in refs]


def test_founder_report_with_alias(client, judged):
    r = client.post("/api/founder/analyze", json={"company_id": SENSOFUSION_ALIAS})
    assert r.status_code == 200
    report = FounderReport.model_validate(r.json())
    assert report.company.id == SENSOFUSION and judged == [SENSOFUSION]
    assert [c.company.id for c in report.competitors] == RIVALS[SENSOFUSION]


def test_founder_report_conflict_and_memo(client, judged):
    for _ in range(2):
        report = FounderReport.model_validate(
            client.post("/api/founder/analyze", json={"company_id": STENDR}).json()
        )
    assert judged == [STENDR]  # second call reuses the judged competitors
    nif = next(s for s in report.skip if s.investor.id == NIF)
    assert nif.conflicts[0].competitor.id == KELLUU


def test_founder_report_with_competitor_ids(client, judged):
    client.post("/api/founder/analyze", json={"company_id": STENDR})
    body = {"company_id": STENDR, "competitor_ids": [SENSOFUSION, STENDR, SENSOFUSION]}
    report = FounderReport.model_validate(client.post("/api/founder/analyze", json=body).json())
    assert [(c.company.id, c.reason) for c in report.competitors] == [
        (SENSOFUSION, f"judged {SENSOFUSION}")
    ]
    assert NIF not in {s.investor.id for s in report.skip}  # Kelluu removed -> no NIF conflict
    assert judged == [STENDR]

    fresh = {"company_id": SENSOFUSION, "competitor_ids": [KELLUU, NESTAI]}
    report = FounderReport.model_validate(client.post("/api/founder/analyze", json=fresh).json())
    assert [c.reason for c in report.competitors] == [f"judged {KELLUU}", "Chosen by you"]
    assert judged == [STENDR, SENSOFUSION]  # not judged yet -> judged once, for the reasons


def test_investor_check(client):
    pair = {"investor_id": NIF, "company_id": STENDR}
    check = InvestorCheck.model_validate(client.post("/api/investor/check", json=pair).json())
    assert check.investor.id == NIF and check.company.id == STENDR
    assert [c.competitor.id for c in check.conflicts] == [KELLUU]
    assert {rd.company_id for rd in check.rounds} <= {STENDR, KELLUU, SENSOFUSION}
    assert any(rd.company_id == KELLUU for rd in check.rounds)


def test_brief(client, monkeypatch):
    async def fake(prompt, schema, **kw):
        return schema.model_validate(
            {"sections": [{"heading": "Verdict", "sentences": [{"text": "Fits.", "facts": [2]}]}]}
        )

    monkeypatch.setattr(briefs, "structured", fake)
    pair = {"investor_id": MAKI, "company_id": STENDR}
    brief = Brief.model_validate(client.post("/api/brief", json=pair).json())
    assert brief.markdown.startswith("## Verdict\n\nFits. [1]") and brief.citations


def test_gemini_unavailable_is_503(client, monkeypatch):
    async def down(company, graph):
        raise LLMError("GEMINI_API_KEY is not set in .env")

    monkeypatch.setattr(api, "cached_judge", down)
    r = client.post("/api/founder/analyze", json={"company_id": STENDR})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["error"]


def test_slush_prep_stream(client):
    body = {"company_id": KELLUU, "investor_names": ["Maki.vc"]}
    job_id = client.post("/api/slush-prep", json=body).json()["job_id"]
    assert events(client.get(f"/api/jobs/{job_id}/stream"))[-1].type == "done"


def test_chat_stream(client):
    assert events(client.post("/api/chat", json={"message": "hi"}))[-1].type == "done"


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("post", "/api/resolve", {"name": "x", "kind": "fund"}, 422),
        ("post", "/api/chat", {"message": ""}, 422),
        ("post", "/api/founder/analyze", {"company_id": "nope"}, 404),
        ("post", "/api/investor/check", {"investor_id": "nope", "company_id": "x"}, 404),
        ("post", "/api/brief", {"investor_id": "../../x", "company_id": "y"}, 404),
        ("get", "/api/jobs/nope/stream", None, 404),
        ("get", "/api/nope", None, 404),
    ],
)
def test_errors_are_json(client, method, path, body, status):
    r = client.request(method, path, json=body)
    assert r.status_code == status
    assert isinstance(r.json()["error"], str)
