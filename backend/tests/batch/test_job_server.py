"""The Verda batch-job wrapper: health check, one job, then exit."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from batch import job_server


@pytest.fixture
def server(monkeypatch):
    job_server._Handler.exit_code = None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), job_server._Handler)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    yield httpd, thread, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    thread.join(timeout=5)
    httpd.server_close()


def get(url, method="GET"):
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_health_does_not_start_or_end_the_job(server):
    _, thread, url = server
    assert get(f"{url}/health") == (200, {"ok": True})
    assert thread.is_alive() and job_server._Handler.exit_code is None


def test_one_request_runs_the_job_with_its_options_then_the_server_stops(server, monkeypatch):
    seen = {}

    async def fake_job(options):
        seen.update(options)
        return {"crawl": {"crawled": 3}, "derive": {"investors": 3}}

    monkeypatch.setattr(job_server, "run_job", fake_job)
    _, thread, url = server
    status, body = get(f"{url}/run?max_investors=5&per_minute=6&seeds=Kelluu,Stendr", "POST")
    assert status == 200 and body == {
        "ok": True,
        "crawl": {"crawled": 3},
        "derive": {"investors": 3},
    }
    assert seen == {"max_investors": "5", "per_minute": "6", "seeds": "Kelluu,Stendr"}
    thread.join(timeout=5)
    assert not thread.is_alive() and job_server._Handler.exit_code == 0


def test_a_failed_job_answers_500_and_exits_non_zero(server, monkeypatch):
    async def broken_job(options):
        raise RuntimeError("Cala is down")

    monkeypatch.setattr(job_server, "run_job", broken_job)
    _, thread, url = server
    assert get(f"{url}/run", "POST") == (500, {"ok": False, "error": "Cala is down"})
    thread.join(timeout=5)
    assert job_server._Handler.exit_code == 1
