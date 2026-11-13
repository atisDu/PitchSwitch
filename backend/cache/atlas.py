"""MongoDB Atlas cache for Cala responses (task A10).

Plugs into `CalaClient(cache=...)`. One document per distinct Cala request:

    {_id: "<METHOD> <path>[#<hash of the input>]", endpoint, response_json, stored_at, expires_at}

- Entries are fresh for 24 hours. A fresh entry is served without calling Cala.
- An expired entry is kept, not deleted. It is served when Cala can't be reached (rate limit,
  outage) and in CACHE_ONLY mode, so the demo keeps working with no network to Cala.
- `response_json` is Cala's JSON as text, so it comes back exactly as it went in.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

from data.config import env, load_env
from data.errors import Upstream

COLLECTION = "cala_cache"
DEFAULT_TTL = 24 * 60 * 60
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class CacheUnavailable(Upstream):
    """MongoDB is not configured or can't be reached."""


class AtlasCache:
    """A `ResponseCache` (see data.cala_client) on a MongoDB collection."""

    def __init__(
        self,
        collection: Any,
        *,
        ttl: float = DEFAULT_TTL,
        clock: Callable[[], float] = time.time,
        client: Any = None,
    ) -> None:
        self.collection = collection
        self.ttl = ttl
        self._clock = clock
        self._client = client

    @classmethod
    def from_env(cls, **kwargs: Any) -> AtlasCache:
        """The cache on MONGODB_URI / MONGODB_DB. Raises CacheUnavailable if the URI is empty."""
        load_env()
        uri = env("MONGODB_URI")
        if not uri:
            raise CacheUnavailable("MONGODB_URI is empty: put it in .env (see .env.example).")
        from pymongo import AsyncMongoClient

        client = AsyncMongoClient(uri, serverSelectionTimeoutMS=8000, appname="pitchlist")
        database = client[env("MONGODB_DB", "pitchlist") or "pitchlist"]
        return cls(database[COLLECTION], client=client, **kwargs)

    async def ping(self) -> None:
        """Raise CacheUnavailable unless MongoDB answers."""
        try:
            await self.collection.database.command("ping")
        except Exception as exc:  # pymongo raises many types; all mean "can't use the cache"
            raise CacheUnavailable(f"MongoDB is not reachable: {exc!r}") from exc

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()

    # --- ResponseCache -----------------------------------------------------------------------

    async def get(self, key: str) -> dict | None:
        """The response for this request if it was stored less than `ttl` seconds ago."""
        document = await self.collection.find_one({"_id": key})
        if document is None or document.get("expires_at", 0) <= self._clock():
            return None
        return json.loads(document["response_json"])

    async def get_stale(self, key: str) -> dict | None:
        """The response for this request however old it is (CACHE_ONLY, or Cala is down)."""
        document = await self.collection.find_one({"_id": key})
        return json.loads(document["response_json"]) if document else None

    async def set(self, key: str, value: dict) -> None:
        now = self._clock()
        await self.collection.replace_one(
            {"_id": key},
            {
                "_id": key,
                "endpoint": _UUID.sub("{id}", key.split("#", 1)[0]),
                "response_json": json.dumps(value, ensure_ascii=False),
                "stored_at": now,
                "expires_at": now + self.ttl,
            },
            upsert=True,
        )

    # --- Housekeeping --------------------------------------------------------------------------

    async def count(self) -> dict:
        """How many responses are cached, and how many of them are still fresh."""
        total = await self.collection.count_documents({})
        fresh = await self.collection.count_documents({"expires_at": {"$gt": self._clock()}})
        return {"total": total, "fresh": fresh, "stale": total - fresh}
