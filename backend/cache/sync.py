"""Copy this machine's local cache into MongoDB Atlas, so the whole team shares it.

    python -m cache.sync

Before MONGODB_URI was set, Cala responses were cached in .cache/cala/ and the batch job wrote
to .cache/graph/. This uploads both. A document Atlas already has in a newer version is left
alone, so it is safe to run from several machines and to run twice. Nothing calls Cala.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cache.atlas import AtlasCache
from cache.files import DEFAULT_DIR as CALA_DIR
from cache.graph import DEFAULT_DIR as GRAPH_DIR
from cache.graph import AtlasGraph, FileGraph, GraphDB


def _age(document: dict | None) -> float:
    """When a precomputed document was written (crawl or derive time); 0 if unknown."""
    document = document or {}
    return float(document.get("derived_at") or document.get("crawled_at") or 0)


async def sync_responses(directory: Path, cache: AtlasCache) -> dict:
    """Upload cached Cala responses. Returns {"uploaded", "kept"} (kept = Atlas had it as new)."""
    counts = {"uploaded": 0, "kept": 0}
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        try:
            local = json.loads(path.read_text())
            key, stored_at, response = local["key"], float(local["stored_at"]), local["response"]
        except (OSError, ValueError, KeyError):
            continue  # a damaged file is not worth stopping for
        remote = await cache.stored_at(key)
        if remote is not None and remote >= stored_at:
            counts["kept"] += 1
            continue
        await cache.set(key, response, stored_at=stored_at)
        counts["uploaded"] += 1
    return counts


async def sync_graph(local: FileGraph, remote: GraphDB) -> dict:
    """Upload precomputed documents, collection by collection."""
    counts = {"uploaded": 0, "kept": 0}
    folders = (
        sorted(p.name for p in local.dir.iterdir() if p.is_dir()) if local.dir.exists() else []
    )
    for collection in folders:
        for doc_id in await local.ids(collection):
            document = await local.get(collection, doc_id)
            existing = await remote.get(collection, doc_id)
            if existing is not None and _age(existing) >= _age(document):
                counts["kept"] += 1
                continue
            await remote.put(collection, doc_id, document)
            counts["uploaded"] += 1
    return counts


async def _main() -> int:
    cache = AtlasCache.from_env()  # raises a clear error when MONGODB_URI is empty
    graph = AtlasGraph.from_env()
    try:
        await cache.ping()
        print("Cala responses:", await sync_responses(CALA_DIR, cache))
        print("precomputed graph:", await sync_graph(FileGraph(GRAPH_DIR), graph))
        print("Atlas cache now holds:", await cache.count())
    finally:
        await cache.aclose()
        await graph.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
