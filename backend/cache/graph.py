"""Where the batch job keeps what it precomputes: small JSON documents in named collections.

    crawl_investors     what Cala says about one investor (profile, portfolio, rounds)
    investor_graph      who co-invests with whom, with counts
    investor_activity   last lead, deals in the last 12 months, rounds per stage

Two interchangeable backends: MongoDB Atlas (shared by the team and the deployed server) when
MONGODB_URI is set, else files under .cache/graph/ on this machine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

from data.config import REPO_ROOT, env, load_env

DEFAULT_DIR = REPO_ROOT / ".cache" / "graph"
_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


class GraphDB(Protocol):
    async def get(self, collection: str, doc_id: str) -> dict | None: ...
    async def put(self, collection: str, doc_id: str, document: dict) -> None: ...
    async def ids(self, collection: str) -> list[str]: ...


class MemoryGraph:
    """For tests."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, dict]] = {}

    async def get(self, collection: str, doc_id: str) -> dict | None:
        return self.data.get(collection, {}).get(doc_id)

    async def put(self, collection: str, doc_id: str, document: dict) -> None:
        self.data.setdefault(collection, {})[doc_id] = json.loads(json.dumps(document))

    async def ids(self, collection: str) -> list[str]:
        return sorted(self.data.get(collection, {}))


class FileGraph:
    """One JSON file per document: <dir>/<collection>/<id>.json."""

    def __init__(self, directory: Path = DEFAULT_DIR) -> None:
        self.dir = directory

    def _path(self, collection: str, doc_id: str) -> Path:
        return self.dir / _SAFE.sub("_", collection) / f"{_SAFE.sub('_', doc_id)}.json"

    async def get(self, collection: str, doc_id: str) -> dict | None:
        try:
            return json.loads(self._path(collection, doc_id).read_text())["document"]
        except (OSError, ValueError, KeyError):
            return None

    async def put(self, collection: str, doc_id: str, document: dict) -> None:
        path = self._path(collection, doc_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"id": doc_id, "document": document}, ensure_ascii=False))
        temporary.replace(path)

    async def ids(self, collection: str) -> list[str]:
        folder = self.dir / _SAFE.sub("_", collection)
        found = []
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            try:
                found.append(json.loads(path.read_text())["id"])
            except (OSError, ValueError, KeyError):
                continue
        return found


class AtlasGraph:
    """One MongoDB collection per name: {_id: <id>, document: {...}}."""

    def __init__(self, database: Any, client: Any = None) -> None:
        self.database = database
        self._client = client

    @classmethod
    def from_env(cls) -> AtlasGraph:
        load_env()
        from pymongo import AsyncMongoClient

        client = AsyncMongoClient(
            env("MONGODB_URI"), serverSelectionTimeoutMS=8000, appname="pitchlist"
        )
        return cls(client[env("MONGODB_DB", "pitchlist") or "pitchlist"], client)

    async def get(self, collection: str, doc_id: str) -> dict | None:
        found = await self.database[collection].find_one({"_id": doc_id})
        return found["document"] if found else None

    async def put(self, collection: str, doc_id: str, document: dict) -> None:
        await self.database[collection].replace_one(
            {"_id": doc_id}, {"_id": doc_id, "document": document}, upsert=True
        )

    async def ids(self, collection: str) -> list[str]:
        return sorted([row["_id"] async for row in self.database[collection].find({}, {"_id": 1})])

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()


def default_graph() -> GraphDB:
    """Atlas when MONGODB_URI is set, else local files."""
    load_env()
    return AtlasGraph.from_env() if env("MONGODB_URI") else FileGraph()
