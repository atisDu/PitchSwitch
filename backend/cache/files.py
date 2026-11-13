"""A cache of Cala responses in local files, for running without MongoDB.

Same behaviour as `cache.atlas.AtlasCache` (fresh for 24 hours, expired entries kept as a
fallback), one JSON file per request under .cache/cala/ in the repo (gitignored). Used when
MONGODB_URI is empty, so local runs don't spend Cala's 10 calls a minute twice.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

from data.config import REPO_ROOT

DEFAULT_DIR = REPO_ROOT / ".cache" / "cala"
DEFAULT_TTL = 24 * 60 * 60


class FileCache:
    """A `ResponseCache` (see data.cala_client) on a folder of JSON files."""

    def __init__(
        self,
        directory: Path = DEFAULT_DIR,
        *,
        ttl: float = DEFAULT_TTL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.dir = directory
        self.ttl = ttl
        self._clock = clock

    def _path(self, key: str) -> Path:
        return self.dir / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"

    def _read(self, key: str) -> dict | None:
        path = self._path(key)
        try:
            document = json.loads(path.read_text())
        except (OSError, ValueError):
            return None  # missing or half-written: a miss
        return document if document.get("key") == key else None

    async def get(self, key: str) -> dict | None:
        document = self._read(key)
        if document is None or document.get("expires_at", 0) <= self._clock():
            return None
        return document["response"]

    async def get_stale(self, key: str) -> dict | None:
        document = self._read(key)
        return document["response"] if document else None

    async def set(self, key: str, value: dict) -> None:
        now = self._clock()
        self.dir.mkdir(parents=True, exist_ok=True)
        document = {"key": key, "stored_at": now, "expires_at": now + self.ttl, "response": value}
        path = self._path(key)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False))
        temporary.replace(path)  # atomic: readers never see a half-written file

    async def count(self) -> dict:
        now, total, fresh = self._clock(), 0, 0
        for path in self.dir.glob("*.json") if self.dir.exists() else []:
            try:
                expires_at = json.loads(path.read_text()).get("expires_at", 0)
            except (OSError, ValueError):
                continue
            total += 1
            fresh += expires_at > now
        return {"total": total, "fresh": fresh, "stale": total - fresh}
