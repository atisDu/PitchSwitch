"""AtlasCache on a fake collection, plus a real-MongoDB check when MONGODB_TEST_URI is set."""

import os
import uuid

import httpx
import pytest

from cache.atlas import AtlasCache, CacheUnavailable
from data.cala_client import CacheOnlyMiss, CalaClient, CalaError, cache_key

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"


class FakeCollection:
    """The few collection methods AtlasCache uses, in memory."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    async def find_one(self, query):
        return self.docs.get(query["_id"])

    async def replace_one(self, query, document, upsert=False):
        self.docs[query["_id"]] = document

    async def count_documents(self, query):
        if not query:
            return len(self.docs)
        limit = query["expires_at"]["$gt"]
        return sum(doc["expires_at"] > limit for doc in self.docs.values())


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cache(clock):
    return AtlasCache(FakeCollection(), clock=clock)


async def test_a_stored_response_comes_back_unchanged(cache):
    value = {"name": "Kelluu Oy", "nested": {"a.b": [1, 2.5, None, "ö"]}, "$odd": True}
    key = cache_key("POST", f"/entities/{KELLUU}", None, {"properties": ["name"]})
    assert await cache.get(key) is None
    await cache.set(key, value)
    assert await cache.get(key) == value

    document = cache.collection.docs[key]
    assert document["endpoint"] == "POST /entities/{id}"
    assert document["expires_at"] - document["stored_at"] == 24 * 60 * 60


async def test_entries_expire_after_24_hours_but_stay_available_as_stale(cache, clock):
    await cache.set("k", {"n": 1})
    clock.now += 24 * 60 * 60 - 1
    assert await cache.get("k") == {"n": 1}
    clock.now += 2
    assert await cache.get("k") is None
    assert await cache.get_stale("k") == {"n": 1}
    assert await cache.get_stale("missing") is None
    assert await cache.count() == {"total": 1, "fresh": 0, "stale": 1}

    await cache.set("k", {"n": 2})  # storing again makes it fresh
    assert await cache.get("k") == {"n": 2}
    assert await cache.count() == {"total": 1, "fresh": 1, "stale": 0}


def test_from_env_needs_a_uri(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "")
    with pytest.raises(CacheUnavailable):
        AtlasCache.from_env()


# --- with the Cala client ------------------------------------------------------------------------


def client_with(cache, handler, **kwargs):
    async def no_sleep(seconds):
        pass

    return CalaClient(
        "k",
        "https://cala.test/v1",
        cache=cache,
        per_minute=0,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
        **kwargs,
    )


async def test_the_client_reads_and_writes_through_the_cache(cache):
    hits = []

    def handler(request):
        hits.append(request)
        return httpx.Response(200, json={"n": len(hits)})

    client = client_with(cache, handler)
    assert await client.query("q") == {"n": 1}
    assert await client.query("q") == {"n": 1}
    assert len(hits) == 1 and [c.cache_hit for c in client.calls] == [False, True]


async def test_an_expired_answer_is_refreshed_when_cala_works(cache, clock):
    replies = iter([{"v": "old"}, {"v": "new"}])
    client = client_with(cache, lambda request: httpx.Response(200, json=next(replies)))
    assert await client.query("q") == {"v": "old"}
    clock.now += 25 * 60 * 60
    assert await client.query("q") == {"v": "new"}
    assert await cache.get(cache_key("POST", "/knowledge/query", None, {"input": "q"})) == {
        "v": "new"
    }


async def test_an_expired_answer_is_served_when_cala_is_down(cache, clock):
    up = True

    def handler(request):
        if up:
            return httpx.Response(200, json={"v": "old"})
        return httpx.Response(429, json={"error": "rate_limit_exceeded"})

    client = client_with(cache, handler, max_retries=1)
    assert await client.query("q") == {"v": "old"}
    clock.now += 25 * 60 * 60
    up = False
    assert await client.query("q") == {"v": "old"}  # stale, but better than an error
    assert client.calls[-1].cache_hit
    with pytest.raises(CalaError):
        await client.query("never seen")


async def test_cache_only_serves_stale_and_never_calls_cala(cache, clock):
    def handler(request):
        raise AssertionError("network used in CACHE_ONLY mode")

    await cache.set(cache_key("POST", "/knowledge/query", None, {"input": "known"}), {"v": 1})
    clock.now += 100 * 60 * 60
    client = client_with(cache, handler, cache_only=True)
    assert await client.query("known") == {"v": 1}
    with pytest.raises(CacheOnlyMiss):
        await client.query("unknown")


async def test_a_broken_cache_does_not_break_calls():
    class Broken:
        async def get(self, key):
            raise ConnectionError("mongo down")

        async def set(self, key, value):
            raise ConnectionError("mongo down")

    client = client_with(Broken(), lambda request: httpx.Response(200, json={"ok": True}))
    assert await client.query("q") == {"ok": True}

    offline = client_with(Broken(), lambda request: httpx.Response(200, json={}), cache_only=True)
    with pytest.raises(ConnectionError):
        await offline.query("q")


# --- real MongoDB --------------------------------------------------------------------------------


@pytest.mark.skipif(not os.environ.get("MONGODB_TEST_URI"), reason="MONGODB_TEST_URI not set")
async def test_round_trip_on_a_real_mongodb(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", os.environ["MONGODB_TEST_URI"])
    monkeypatch.setenv("MONGODB_DB", f"pitchlist_test_{uuid.uuid4().hex[:8]}")
    cache = AtlasCache.from_env()
    try:
        await cache.ping()
        value = {"name": "Kelluu Oy", "nested": {"a.b": [1, 2.5, None, "ö"]}, "$odd": True}
        await cache.set("POST /entities/x#abc", value)
        assert await cache.get("POST /entities/x#abc") == value
        assert await cache.get_stale("POST /entities/x#abc") == value
        await cache.set("POST /entities/x#abc", {"v": 2})
        assert await cache.get("POST /entities/x#abc") == {"v": 2}
        assert await cache.count() == {"total": 1, "fresh": 1, "stale": 0}
    finally:
        await cache.collection.database.client.drop_database(cache.collection.database.name)
        await cache.aclose()
