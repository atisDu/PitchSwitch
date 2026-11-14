"""CalaClient against a mocked HTTP transport: no network, no real waiting."""

import asyncio
import json

import httpx
import pytest

from data.cala_client import (
    CacheOnlyMiss,
    CalaClient,
    CalaError,
    MemoryCache,
    cache_key,
)
from data.errors import NotFound, Upstream

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"


class FakeTime:
    """A clock that only moves when the client sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, **kwargs):
    fake = FakeTime()
    kwargs.setdefault("per_minute", 0)  # no rate limit unless a test asks for one
    client = CalaClient(
        "test-key",
        "https://cala.test/v1/",
        transport=httpx.MockTransport(handler),
        sleep=fake.sleep,
        clock=fake.clock,
        **kwargs,
    )
    return client, fake


def replies(*responses):
    """A handler that answers with the given responses in order and counts the requests."""
    queue = list(responses)
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    return handler, seen


async def test_search_sends_the_key_and_returns_calas_json():
    handler, seen = replies(httpx.Response(200, json={"entities": [{"id": KELLUU}]}))
    client, _ = make_client(handler)
    async with client:
        result = await client.search_entities("Kelluu", entity_types=["Company"], limit=5)

    assert result == {"entities": [{"id": KELLUU}]}
    request = seen[0]
    assert request.method == "GET" and request.url.path == "/v1/entities"
    assert request.headers["X-API-KEY"] == "test-key"
    assert request.url.params["name"] == "Kelluu" and request.url.params["limit"] == "5"
    assert request.url.params.get_list("entity_types") == ["Company"]


async def test_entity_builds_the_projection_body():
    handler, seen = replies(httpx.Response(200, json={"id": KELLUU}))
    client, _ = make_client(handler)
    await client.entity(
        KELLUU, properties=["name"], outgoing=["INVESTED_IN"], incoming=["FOUNDED"], limit=7
    )
    await client.introspect(KELLUU)
    await client.query("companies.country=Finland")
    await client.search("Who led Kelluu's Series A?")

    assert seen[0].url.path == f"/v1/entities/{KELLUU}"
    assert json.loads(seen[0].content) == {
        "properties": ["name"],
        "relationships": {
            "outgoing": {"INVESTED_IN": {"limit": 7}},
            "incoming": {"FOUNDED": {"limit": 7}},
        },
    }
    assert seen[1].method == "GET" and seen[1].url.path.endswith("/introspection")
    assert seen[2].url.path == "/v1/knowledge/query"
    assert json.loads(seen[3].content) == {"input": "Who led Kelluu's Series A?"}
    assert [c.endpoint for c in client.calls] == [
        "POST /entities/{id}",
        "GET /entities/{id}/introspection",
        "POST /knowledge/query",
        "POST /knowledge/search",
    ]


async def test_server_errors_are_retried_with_backoff():
    handler, seen = replies(
        httpx.Response(503), httpx.Response(502), httpx.Response(200, json={"ok": True})
    )
    client, fake = make_client(handler)
    assert await client.query("q") == {"ok": True}
    assert len(seen) == 3 and fake.sleeps == [2.0, 4.0]
    assert client.calls[0].attempts == 3 and client.calls[0].status == 200


async def test_rate_limit_replies_wait_longer():
    handler, seen = replies(
        httpx.Response(429, json={"error": "rate_limit_exceeded"}),
        httpx.Response(429),
        httpx.Response(200, json={"ok": True}),
    )
    client, fake = make_client(handler)
    assert await client.query("q") == {"ok": True}
    assert fake.sleeps == [15.0, 30.0]


async def test_network_errors_are_retried_then_reported():
    handler, seen = replies(httpx.ConnectError("down"))
    client, fake = make_client(handler, max_retries=2)
    with pytest.raises(CalaError) as failure:
        await client.query("q")
    assert isinstance(failure.value, Upstream) and failure.value.status == 0
    assert len(seen) == 3 and fake.sleeps == [2.0, 4.0]
    assert client.stats()["failed"] == 1


async def test_unknown_entity_is_not_found_and_not_retried():
    handler, seen = replies(httpx.Response(404, json={"error": "not_found"}))
    client, fake = make_client(handler)
    with pytest.raises(NotFound):
        await client.entity(KELLUU)
    assert len(seen) == 1 and fake.sleeps == []


async def test_a_bad_request_is_not_retried():
    handler, seen = replies(httpx.Response(401, text="invalid api key"))
    client, fake = make_client(handler)
    with pytest.raises(CalaError) as failure:
        await client.query("q")
    assert failure.value.status == 401 and "invalid api key" in str(failure.value)
    assert len(seen) == 1 and fake.sleeps == []


async def test_at_most_per_minute_requests_start_in_a_minute():
    handler, seen = replies(httpx.Response(200, json={}))
    client, fake = make_client(handler, per_minute=2)
    for i in range(5):
        await client.query(f"q{i}")
    assert len(seen) == 5
    assert fake.sleeps == [60.0, 60.0]  # calls 3 and 5 each wait for the window to move on
    assert fake.now == 120.0


async def test_cached_responses_skip_the_network():
    handler, seen = replies(httpx.Response(200, json={"n": 1}))
    cache = MemoryCache()
    client, _ = make_client(handler, cache=cache)
    assert await client.search("who?") == {"n": 1}
    assert await client.search("who?") == {"n": 1}
    assert await client.search("who else?") == {"n": 1}
    assert len(seen) == 2 and len(cache) == 2
    assert [c.cache_hit for c in client.calls] == [False, True, False]
    assert client.stats() == {
        "calls": 3,
        "cache_hits": 1,
        "http_requests": 2,
        "failed": 0,
        "by_endpoint": {"POST /knowledge/search": 2},
    }


async def test_cache_only_never_calls_cala():
    def handler(request):
        raise AssertionError("network used in CACHE_ONLY mode")

    cache = MemoryCache()
    await cache.set(cache_key("POST", "/knowledge/query", None, {"input": "known"}), {"rows": 1})
    client, _ = make_client(handler, cache=cache, cache_only=True)
    assert await client.query("known") == {"rows": 1}
    with pytest.raises(CacheOnlyMiss):
        await client.query("unknown")


async def test_identical_requests_at_the_same_time_share_one_call():
    started = asyncio.Event()
    release = asyncio.Event()
    count = 0

    async def handler(request):
        nonlocal count
        count += 1
        started.set()
        await release.wait()
        return httpx.Response(200, json={"id": KELLUU})

    client, _ = make_client(handler)
    first = asyncio.create_task(client.entity(KELLUU, properties=["name"]))
    await started.wait()
    second = asyncio.create_task(client.entity(KELLUU, properties=["name"]))
    await asyncio.sleep(0)
    release.set()
    assert await first == await second == {"id": KELLUU}
    assert count == 1


async def test_a_failed_shared_call_fails_for_everyone_waiting():
    release = asyncio.Event()

    async def handler(request):
        await release.wait()
        return httpx.Response(404)

    client, _ = make_client(handler)
    tasks = [asyncio.create_task(client.entity(KELLUU)) for _ in range(2)]
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(result, NotFound) for result in results)


async def test_no_more_than_concurrency_requests_run_at_once():
    running = 0
    peak = 0

    async def handler(request):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return httpx.Response(200, json={})

    client, _ = make_client(handler, concurrency=2)
    await asyncio.gather(*[client.query(f"q{i}") for i in range(6)])
    assert peak == 2


def test_cache_key_is_stable_and_depends_on_the_input():
    plain = cache_key("GET", f"/entities/{KELLUU}/introspection", None, None)
    assert plain == f"GET /entities/{KELLUU}/introspection"
    one = cache_key("POST", "/knowledge/query", None, {"input": "a", "x": 1})
    same = cache_key("POST", "/knowledge/query", None, {"x": 1, "input": "a"})
    other = cache_key("POST", "/knowledge/query", None, {"input": "b"})
    assert one == same and one != other and one.startswith("POST /knowledge/query#")


def test_from_env_needs_a_key(monkeypatch):
    monkeypatch.setenv("CALA_API_KEY", "")
    with pytest.raises(CalaError):
        CalaClient.from_env()
    monkeypatch.setenv("CALA_API_KEY", "k")
    monkeypatch.setenv("CALA_BASE_URL", "https://cala.test/v1")
    assert CalaClient.from_env(per_minute=3).per_minute == 3


async def test_a_failing_cache_is_left_alone_for_a_minute_then_tried_again():
    attempts = []

    class Flaky:
        down = True

        async def get(self, key):
            attempts.append("get")
            if self.down:
                raise ConnectionError("database unreachable")
            return None

        async def set(self, key, value):
            attempts.append("set")

    cache = Flaky()
    handler, seen = replies(httpx.Response(200, json={"ok": True}))
    client, fake = make_client(handler, cache=cache)
    for i in range(5):
        assert await client.query(f"q{i}") == {"ok": True}
    assert attempts == ["get"] and len(seen) == 5  # one failed read, then the cache is skipped

    fake.now += 61
    cache.down = False
    await client.query("later")
    assert attempts == ["get", "get", "set"]


async def test_require_cache_refuses_to_call_cala_when_the_cache_is_down():
    from data.cala_client import CacheUnavailable

    class Down:
        async def get(self, key):
            raise ConnectionError("database unreachable")

        async def set(self, key, value):
            raise ConnectionError("database unreachable")

    handler, seen = replies(httpx.Response(200, json={"ok": True}))
    client, fake = make_client(handler, cache=Down(), require_cache=True)
    with pytest.raises(CacheUnavailable):
        await client.query("q1")
    with pytest.raises(CacheUnavailable):
        await client.query("q2")
    assert seen == []  # nothing reached Cala

    relaxed, _ = make_client(handler, cache=Down())  # the default: carry on without the cache
    assert await relaxed.query("q1") == {"ok": True}


def test_the_default_rate_leaves_room_under_calas_limit_and_env_can_change_it(monkeypatch):
    from data.cala_client import DEFAULT_PER_MINUTE

    assert 0 < DEFAULT_PER_MINUTE < 100  # Cala allows 100 a minute on the shared key
    monkeypatch.setenv("CALA_API_KEY", "k")
    monkeypatch.setenv("CALA_PER_MINUTE", "")
    assert CalaClient.from_env().per_minute == DEFAULT_PER_MINUTE
    monkeypatch.setenv("CALA_PER_MINUTE", "25")
    assert CalaClient.from_env().per_minute == 25
    assert CalaClient.from_env(per_minute=5).per_minute == 5  # an explicit argument wins
