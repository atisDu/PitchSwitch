"""Async client for the Cala REST API (task A3). The only code that talks to Cala.

    async with CalaClient.from_env() as cala:
        hits = await cala.search_entities("Kelluu")
        entity = await cala.entity(hits["entities"][0]["id"], properties=["name"])

What it takes care of:
- `X-API-KEY` auth, timeouts, and retries with backoff on 429, 5xx and network errors;
- Cala's rate limit (100 calls a minute on our key since 14 Nov; it was 10): calls wait their
  turn instead of failing. Each process keeps to 60 a minute by default (CALA_PER_MINUTE),
  because laptops, the server and the batch job share the one key;
- a concurrency cap, and sharing one request between callers that ask for the same thing at once;
- an optional response cache (task A10 plugs MongoDB Atlas in here);
- a log line and a `CallRecord` per call (endpoint, ms, cache hit) to track credit use.

Every method returns Cala's JSON unchanged; `data.mappers` turns it into contract models.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import Counter, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from data.config import env, load_env
from data.errors import NotFound, Upstream

log = logging.getLogger("data.cala")

DEFAULT_BASE_URL = "https://api.cala.ai/v1"
_CACHE_PAUSE = 60  # seconds without the cache after it failed
# Cala allows 100 calls a minute per key. One process takes at most 60 of them, so two busy
# processes (say the server and a laptop) still fit; override with CALA_PER_MINUTE.
DEFAULT_PER_MINUTE = 60
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class CalaError(Upstream):
    """Cala answered with an error we can't recover from, or kept failing after retries."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class CacheOnlyMiss(Upstream):
    """CACHE_ONLY is on and this request is not in the cache."""


class CacheUnavailable(Upstream):
    """The cache can't be reached and this client is set to never call Cala without it."""


class ResponseCache(Protocol):
    """Where responses are kept between calls. `key` is stable for a given request."""

    async def get(self, key: str) -> dict | None: ...
    async def set(self, key: str, value: dict) -> None: ...


class MemoryCache:
    """A cache for one process: tests, scripts, and local runs without MongoDB."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    async def get(self, key: str) -> dict | None:
        return self._data.get(key)

    async def set(self, key: str, value: dict) -> None:
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)


@dataclass(frozen=True)
class CallRecord:
    """One request as the caller saw it."""

    endpoint: str  # e.g. "POST /entities/{id}"
    status: int  # 200, or the last status seen; 0 = network error
    ms: int
    cache_hit: bool
    attempts: int  # HTTP requests made (0 for a cache hit)


def cache_key(method: str, path: str, params: dict | None, body: dict | None) -> str:
    """`<METHOD> <path>` for a plain entity call, plus a hash of the input when there is one."""
    key = f"{method} {path}"
    if params or body:
        payload = json.dumps({"params": params, "json": body}, sort_keys=True, ensure_ascii=False)
        key += "#" + hashlib.sha256(payload.encode()).hexdigest()[:16]
    return key


class CalaClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        *,
        cache: ResponseCache | None = None,
        cache_only: bool = False,
        require_cache: bool = False,
        concurrency: int = 8,
        per_minute: int = DEFAULT_PER_MINUTE,
        timeout: float = 180.0,
        max_retries: int = 4,
        backoff: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self.cache = cache
        self.cache_only = cache_only
        self.require_cache = require_cache  # refuse to call Cala when the cache is unreachable
        self.per_minute = per_minute
        self.max_retries = max_retries
        self.backoff = backoff
        self._sleep = sleep
        self._clock = clock
        self._slots = asyncio.Semaphore(concurrency)
        self._rate_lock = asyncio.Lock()
        self._recent: deque[float] = deque()  # start times of calls in the last minute
        self._in_flight: dict[str, asyncio.Future] = {}
        self._cache_down_until = 0.0
        self.calls: list[CallRecord] = []

    @classmethod
    def from_env(cls, **kwargs: Any) -> CalaClient:
        """A client from CALA_API_KEY / CALA_BASE_URL in the environment or .env."""
        load_env()
        key = env("CALA_API_KEY")
        if not key and not kwargs.get("cache_only"):
            raise CalaError("CALA_API_KEY is empty: put it in .env (see .env.example).")
        configured = env("CALA_PER_MINUTE")
        if configured.isdigit() and "per_minute" not in kwargs:
            kwargs["per_minute"] = int(configured)
        return cls(key, env("CALA_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL, **kwargs)

    async def __aenter__(self) -> CalaClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- Endpoints -----------------------------------------------------------------------------

    async def search_entities(
        self, name: str, entity_types: list[str] | None = None, limit: int = 10
    ) -> dict:
        """Fuzzy search by name. Returns {"entities": [{id, name, entity_type, description}]}."""
        params: dict[str, Any] = {"name": name, "limit": limit}
        if entity_types:
            params["entity_types"] = entity_types
        return await self.request("GET", "/entities", params=params)

    async def introspect(self, entity_id: str) -> dict:
        """Which properties and relationships this entity has."""
        return await self.request("GET", f"/entities/{entity_id}/introspection")

    async def entity(
        self,
        entity_id: str,
        *,
        properties: list[str] | None = None,
        outgoing: list[str] | None = None,
        incoming: list[str] | None = None,
        limit: int = 100,
    ) -> dict:
        """One entity with the requested properties and relationship edges.

        Unknown property names are ignored by Cala. Raises `NotFound` for an unknown ID.
        """
        body: dict[str, Any] = {}
        if properties:
            body["properties"] = properties
        relationships = {
            direction: {rel: {"limit": limit} for rel in rels}
            for direction, rels in (("outgoing", outgoing), ("incoming", incoming))
            if rels
        }
        if relationships:
            body["relationships"] = relationships
        return await self.request("POST", f"/entities/{entity_id}", body=body or None)

    async def query(self, text: str) -> dict:
        """knowledge_query: structured rows plus the entities they mention. Slow (20-80 s)."""
        return await self.request("POST", "/knowledge/query", body={"input": text})

    async def search(self, text: str) -> dict:
        """knowledge_search: a sourced markdown answer with explainability. Slow (20-80 s)."""
        return await self.request("POST", "/knowledge/search", body={"input": text})

    # --- Request pipeline --------------------------------------------------------------------

    async def request(
        self, method: str, path: str, *, params: dict | None = None, body: dict | None = None
    ) -> dict:
        """Cache, then one shared HTTP request per distinct input."""
        key = cache_key(method, path, params, body)
        endpoint = f"{method} {_UUID.sub('{id}', path)}"
        started = self._clock()

        cached = await self._cache_get(key, allow_stale=self.cache_only)
        if cached is not None:
            self._record(endpoint, 200, started, cache_hit=True, attempts=0)
            return cached
        if self.cache_only:
            raise CacheOnlyMiss(f"CACHE_ONLY is on and {endpoint} is not cached")
        if self.require_cache and self._cache_is_down():
            # A server that cannot reach its cache would pay Cala for every request, again and
            # again. Failing is cheaper than emptying the team's credits.
            raise CacheUnavailable(
                f"the cache is unreachable, so {endpoint} was not sent to Cala "
                "(CALA_REQUIRE_CACHE is on; check MongoDB Atlas network access)"
            )

        waiting = self._in_flight.get(key)
        if waiting is not None:  # someone is already fetching exactly this
            return await asyncio.shield(waiting)

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._in_flight[key] = future
        try:
            try:
                response = await self._fetch(method, path, params, body, endpoint, started)
            except CalaError:
                # Cala is down or rate-limiting us: an old answer beats no answer.
                response = await self._cache_get(key, allow_stale=True)
                if response is None:
                    raise
                log.warning("cala %s failed; serving the expired cached answer", endpoint)
                self._record(endpoint, 200, started, cache_hit=True, attempts=0)
            else:
                await self._cache_set(key, response)
            future.set_result(response)
            return response
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # mark as retrieved when nobody else is waiting
            raise
        finally:
            del self._in_flight[key]

    async def _cache_get(self, key: str, *, allow_stale: bool) -> dict | None:
        """Read the cache. A broken cache is logged and treated as a miss (unless CACHE_ONLY)."""
        if self.cache is None or self._cache_is_down():
            return None
        try:
            found = await self.cache.get(key)
            stale = getattr(self.cache, "get_stale", None)
            if found is None and allow_stale and stale is not None:
                found = await stale(key)
            return found
        except Exception as exc:
            if self.cache_only:
                raise
            self._cache_failed("read", exc)
            return None

    async def _cache_set(self, key: str, value: dict) -> None:
        if self.cache is None or self._cache_is_down():
            return
        try:
            await self.cache.set(key, value)
        except Exception as exc:
            self._cache_failed("write", exc)

    def _cache_is_down(self) -> bool:
        """After a cache failure we stop asking it for a minute: an unreachable database
        costs seconds per attempt, and every Cala call would pay that twice."""
        return not self.cache_only and self._clock() < self._cache_down_until

    def _cache_failed(self, what: str, exc: Exception) -> None:
        self._cache_down_until = self._clock() + _CACHE_PAUSE
        log.warning(
            "cache %s failed; not using the cache for %d s (calling Cala directly): %r",
            what,
            _CACHE_PAUSE,
            exc,
        )

    async def _fetch(
        self,
        method: str,
        path: str,
        params: dict | None,
        body: dict | None,
        endpoint: str,
        started: float,
    ) -> dict:
        status, detail, attempts = 0, "no response", 0
        async with self._slots:
            for attempt in range(self.max_retries + 1):
                await self._wait_for_rate_limit()
                attempts += 1
                try:
                    reply = await self._http.request(method, path, params=params, json=body)
                    status, detail = reply.status_code, reply.text[:200]
                except httpx.HTTPError as exc:
                    status, detail = 0, repr(exc)
                else:
                    if status == 200:
                        self._record(endpoint, 200, started, cache_hit=False, attempts=attempts)
                        return reply.json()
                    if status == 404:
                        self._record(endpoint, 404, started, cache_hit=False, attempts=attempts)
                        raise NotFound(f"Cala has no entity at {path}")
                    if status != 429 and status < 500:
                        break  # our mistake (400, 401, 403, 422): retrying won't help
                if attempt < self.max_retries:
                    delay = min(self.backoff * 2**attempt, 60.0)
                    if status == 429:  # the limit resets by the minute: short waits are wasted
                        delay = min(max(delay, 15.0 * (attempt + 1)), 60.0)
                    log.warning(
                        "cala %s -> %s, retry in %.0f s", endpoint, status or "error", delay
                    )
                    await self._sleep(delay)
        self._record(endpoint, status, started, cache_hit=False, attempts=attempts)
        raise CalaError(f"Cala {endpoint} failed ({status or 'network error'}): {detail}", status)

    async def _wait_for_rate_limit(self) -> None:
        """Let at most `per_minute` requests start in any 60 seconds."""
        if self.per_minute <= 0:
            return
        async with self._rate_lock:
            while True:
                now = self._clock()
                while self._recent and now - self._recent[0] >= 60.0:
                    self._recent.popleft()
                if len(self._recent) < self.per_minute:
                    self._recent.append(now)
                    return
                await self._sleep(60.0 - (now - self._recent[0]))

    def _record(
        self, endpoint: str, status: int, started: float, *, cache_hit: bool, attempts: int
    ) -> None:
        ms = int((self._clock() - started) * 1000)
        self.calls.append(CallRecord(endpoint, status, ms, cache_hit, attempts))
        log.info(
            "cala %s -> %s in %d ms (%s, %d request%s)",
            endpoint,
            status,
            ms,
            "cache hit" if cache_hit else "cache miss",
            attempts,
            "" if attempts == 1 else "s",
        )

    def stats(self) -> dict:
        """Totals for credit tracking: requests sent to Cala, cache hits, calls per endpoint."""
        return {
            "calls": len(self.calls),
            "cache_hits": sum(c.cache_hit for c in self.calls),
            "http_requests": sum(c.attempts for c in self.calls),
            "failed": sum(c.status != 200 for c in self.calls),
            "by_endpoint": dict(Counter(c.endpoint for c in self.calls if not c.cache_hit)),
        }
