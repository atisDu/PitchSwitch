"""The fixture recorder saves raw responses, resumes, and retries (no network)."""

import json

import httpx

from data.record_fixtures import (
    COMPANIES,
    INVESTORS,
    BudgetExceeded,
    Recorder,
    candidate_ids,
    record_all,
    round_ids,
    slug,
)


def make_recorder(tmp_path, handler, **kwargs):
    client = httpx.Client(base_url="https://cala.test/v1", transport=httpx.MockTransport(handler))
    waits = []
    rec = Recorder(
        client, tmp_path, min_interval=0, sleep=waits.append, log=lambda _line: None, **kwargs
    )
    return rec, waits


def test_slug():
    assert slug("Maki.vc") == "maki-vc"
    assert slug("  NATO Innovation Fund ") == "nato-innovation-fund"
    assert slug("SNÖ Ventures") == "sn-ventures"


def test_fetch_saves_the_raw_response_with_its_request(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"entities": [{"id": "1", "name": "Kelluu Oy"}]})

    rec, _ = make_recorder(tmp_path, handler)
    response = rec.search("Kelluu")

    assert response == {"entities": [{"id": "1", "name": "Kelluu Oy"}]}
    assert seen[0].url.path == "/v1/entities" and seen[0].url.params["name"] == "Kelluu"
    saved = json.loads((tmp_path / "entity_search" / "kelluu.json").read_text())
    assert saved["response"] == response
    assert saved["request"] == {
        "method": "GET",
        "path": "/entities",
        "params": {"name": "Kelluu", "limit": 10},
        "json": None,
    }
    assert saved["recorded_at"]


def test_existing_files_are_not_fetched_again(tmp_path):
    hits = []

    def handler(request):
        hits.append(request)
        return httpx.Response(200, json={"n": len(hits)})

    rec, _ = make_recorder(tmp_path, handler)
    assert rec.answer("q", "who?") == {"n": 1}
    assert rec.answer("q", "who?") == {"n": 1}
    assert len(hits) == 1 and rec.calls == 1 and rec.cached == 1

    forced, _ = make_recorder(tmp_path, handler, force=True)
    assert forced.answer("q", "who?") == {"n": 2}


def test_rate_limit_is_retried_then_succeeds(tmp_path):
    replies = [httpx.Response(429, json={"error": "rate_limit_exceeded"})] * 2
    replies.append(httpx.Response(200, json={"ok": True}))

    rec, waits = make_recorder(tmp_path, lambda request: replies.pop(0))
    assert rec.query("k", "companies") == {"ok": True}
    assert waits == [20.0, 30.0] and rec.calls == 3


def test_a_client_error_is_not_saved(tmp_path):
    rec, waits = make_recorder(tmp_path, lambda request: httpx.Response(404, json={"error": "x"}))
    assert rec.entity("missing") is None
    assert rec.failed == ["entity/missing"] and waits == []
    assert not (tmp_path / "entity" / "missing.json").exists()


def test_budget_stops_the_run(tmp_path):
    rec, _ = make_recorder(tmp_path, lambda request: httpx.Response(200, json={}), max_calls=1)
    rec.search("a")
    try:
        rec.search("b")
    except BudgetExceeded:
        return
    raise AssertionError("budget not enforced")


def test_dry_run_calls_nothing(tmp_path):
    def handler(request):
        raise AssertionError("network used in a dry run")

    rec, _ = make_recorder(tmp_path, handler, dry_run=True)
    assert rec.search("Kelluu") is None and rec.calls == 0


def test_round_ids_and_candidate_ids():
    entity = {
        "relationships": {
            "outgoing": {
                "PARTICIPATES_IN_FUNDING_ROUND": [
                    {"id": "r1", "entity_type": "FundingRound"},
                    {"id": "x", "entity_type": "Company"},
                ]
            }
        }
    }
    assert round_ids(entity) == ["r1"]
    assert round_ids(None) == []

    query = {
        "results": [{"name": "Acme Defence"}, {"error": "too complex"}],
        "entities": [
            {
                "id": "c1",
                "name": "ACME DEFENCE OY",
                "entity_type": "Company",
                "mentions": ["Acme Defence"],
            },
            {"id": "c2", "name": "Finland", "entity_type": "Country", "mentions": ["Finland"]},
            {
                "id": "c3",
                "name": "Some Fund",
                "entity_type": "Organization",
                "mentions": ["Some Fund"],
            },
        ],
    }
    assert candidate_ids(query) == ["c1"]
    assert candidate_ids(None) == []


def test_record_all_walks_companies_rounds_and_investors(tmp_path):
    kelluu = COMPANIES["kelluu"]["id"]

    def handler(request):
        path = request.url.path.removeprefix("/v1")
        if path == f"/entities/{kelluu}":
            return httpx.Response(
                200,
                json={
                    "id": kelluu,
                    "relationships": {
                        "outgoing": {
                            "PARTICIPATES_IN_FUNDING_ROUND": [
                                {"id": "round-a", "entity_type": "FundingRound"}
                            ]
                        },
                        "incoming": {
                            "INVESTED_IN": [{"id": "angel-1", "entity_type": "Organization"}],
                            "IS_BOARD_MEMBER_OF": [{"id": "person-1", "entity_type": "Person"}],
                        },
                    },
                },
            )
        if path == "/knowledge/query":
            return httpx.Response(
                200,
                json={
                    "results": [{"name": "Rival"}],
                    "entities": [
                        {"id": "rival-1", "name": "Rival", "entity_type": "Company", "mentions": []}
                    ],
                },
            )
        return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1], "relationships": {}})

    rec, _ = make_recorder(tmp_path, handler)
    manifest = record_all(rec)

    assert manifest["round_ids"] == ["round-a"]
    assert manifest["extra_investor_ids"] == ["angel-1"]
    assert manifest["candidate_company_ids"] == ["rival-1"]
    assert set(manifest["investors"]) == set(INVESTORS)
    for name in (kelluu, "round-a", "angel-1", "rival-1", INVESTORS["tesi"]["id"]):
        assert (tmp_path / "entity" / f"{name}.json").exists(), name
    assert (tmp_path / "introspection" / "Person.json").exists()
    assert (tmp_path / "knowledge_search" / "rounds-kelluu.json").exists()
    assert not rec.failed

    again, _ = make_recorder(tmp_path, handler)
    record_all(again)
    assert again.calls == 0
