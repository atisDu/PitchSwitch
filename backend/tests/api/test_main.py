import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from contracts.schemas import CONTRACT_VERSION, AgentEvent, Brief, FounderReport, InvestorCheck
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
SENSOFUSION_ALIAS = "5c699806-0fea-4e62-a594-717d4d85516c"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"
STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"


@pytest.fixture
def client(monkeypatch):
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


def test_founder_report_with_alias(client):
    r = client.post("/api/founder/analyze", json={"company_id": SENSOFUSION_ALIAS})
    assert r.status_code == 200
    FounderReport.model_validate(r.json())


def test_investor_check_and_brief(client):
    pair = {"investor_id": MAKI, "company_id": STENDR}
    InvestorCheck.model_validate(client.post("/api/investor/check", json=pair).json())
    Brief.model_validate(client.post("/api/brief", json=pair).json())


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
        ("post", "/api/brief", {"investor_id": "../../x", "company_id": "y"}, 404),
        ("get", "/api/jobs/nope/stream", None, 404),
        ("get", "/api/nope", None, 404),
    ],
)
def test_errors_are_json(client, method, path, body, status):
    r = client.request(method, path, json=body)
    assert r.status_code == status
    assert isinstance(r.json()["error"], str)
