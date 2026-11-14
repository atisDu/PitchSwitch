"""Vector search over the companies we have seen (task A13).

Each company's name and description is embedded once (Gemini embeddings) and stored in the shared
graph store, collection `company_vectors`. `neighbours()` then finds the stored companies closest
in meaning to a given one: on MongoDB Atlas with Atlas Vector Search (`$vectorSearch`), elsewhere,
or if the search index is not ready, by comparing against every stored vector in Python (fine for
the few hundred companies we hold).

Speed: a company already stored costs no Gemini call. A search embeds at most the companies that
are new (one batched call) and runs one database query.

Verda's Inference API has no embeddings endpoint, so the embeddings come from Gemini.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from typing import Any, Protocol

from cache.graph import AtlasGraph, GraphDB, default_graph
from contracts.schemas import Company
from data.config import env, load_env

log = logging.getLogger("cache.vector")

COLLECTION = "company_vectors"
INDEX = "company_vectors_index"
DIMENSIONS = 768
DEFAULT_MODEL = "gemini-embedding-001"
_BATCH = 50  # texts per embedding request


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class GeminiEmbedder:
    """Embeddings from Gemini (GEMINI_API_KEY; model from GEMINI_EMBED_MODEL)."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        load_env()
        self.model = model or env("GEMINI_EMBED_MODEL") or DEFAULT_MODEL
        self._key = api_key or env("GEMINI_API_KEY")
        self._client = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._key:
            raise RuntimeError("GEMINI_API_KEY is empty: no embeddings")
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._key)
        from google.genai import types

        config = types.EmbedContentConfig(
            output_dimensionality=DIMENSIONS, task_type="SEMANTIC_SIMILARITY"
        )
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH):
            reply = await self._client.aio.models.embed_content(
                model=self.model, contents=texts[start : start + _BATCH], config=config
            )
            vectors.extend(list(item.values) for item in reply.embeddings)
        return vectors


def company_text(company: Company) -> str:
    """What we embed for a company: its name and what it does."""
    parts = [company.name, company.description or "", " ".join(company.industries)]
    return ". ".join(part.strip().rstrip(".") for part in parts if part and part.strip())


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class VectorStore:
    def __init__(self, graph: GraphDB | None = None, embedder: Embedder | None = None) -> None:
        self.graph = graph or default_graph()
        self.embedder = embedder or GeminiEmbedder()
        self._index_checked = False
        self._stored: dict[str, str] = {}  # company id -> fingerprint of its stored text
        self._query_vectors: dict[str, tuple[str, list[float]]] = {}  # per-process, saves a read

    async def upsert(self, companies: list[Company]) -> int:
        """Store a vector for every company that has none yet, or whose text changed.
        Returns how many were embedded (0 means no Gemini call was made)."""
        unique: dict[str, tuple[Company, str]] = {}
        for company in companies:
            text = company_text(company)
            if text:
                unique.setdefault(company.id, (company, text))
        # Companies this process already knows are stored need no database round trip.
        unsure = [i for i, (_, text) in unique.items() if self._stored.get(i) != _fingerprint(text)]
        self._stored.update(await self._stored_hashes(unsure))
        todo = [unique[i] for i in unsure if self._stored.get(i) != _fingerprint(unique[i][1])]
        if not todo:
            return 0
        vectors = await self.embedder.embed([text for _, text in todo])
        self._stored.update({company.id: _fingerprint(text) for company, text in todo})
        await asyncio.gather(
            *[
                self.graph.put(
                    COLLECTION,
                    company.id,
                    {
                        "company": company.model_dump(mode="json", exclude={"sources"}),
                        "text_hash": _fingerprint(text),
                        "embedding": [float(value) for value in vector],
                    },
                )
                for (company, text), vector in zip(todo, vectors, strict=True)
            ]
        )
        return len(todo)

    async def _stored_hashes(self, ids: list[str]) -> dict[str, str]:
        """Which of these companies are stored, with the fingerprint of their embedded text.
        One query on Atlas (without pulling the vectors); one small read each elsewhere."""
        if not ids:
            return {}
        if isinstance(self.graph, AtlasGraph):
            cursor = self.graph.database[COLLECTION].find(
                {"_id": {"$in": ids}}, {"document.text_hash": 1}
            )
            return {
                row["_id"]: (row.get("document") or {}).get("text_hash", "") async for row in cursor
            }
        documents = await asyncio.gather(*[self.graph.get(COLLECTION, i) for i in ids])
        return {
            i: document.get("text_hash", "")
            for i, document in zip(ids, documents, strict=True)
            if document
        }

    async def neighbours(self, company: Company, k: int = 10) -> list[tuple[Company, float]]:
        """The stored companies closest in meaning to this one, with their similarity (0-1),
        most similar first. The company itself is never included."""
        text_hash = _fingerprint(company_text(company))
        cached = self._query_vectors.get(company.id)
        if cached and cached[0] == text_hash:
            vector = cached[1]
        else:
            stored = await self.graph.get(COLLECTION, company.id)
            if stored and stored.get("embedding") and stored.get("text_hash") == text_hash:
                vector = stored["embedding"]
            else:
                (vector,) = await self.embedder.embed([company_text(company)])
            self._query_vectors[company.id] = (text_hash, vector)
        rows = await self._search(vector, k + 1)
        result = []
        for document, score in rows:
            found = Company.model_validate(document["company"])
            if found.id != company.id:
                result.append((found, round(float(score), 4)))
        return result[:k]

    async def _search(self, vector: list[float], limit: int) -> list[tuple[dict, float]]:
        if isinstance(self.graph, AtlasGraph):
            try:
                return await self._atlas_search(vector, limit)
            except Exception as exc:  # index missing or still building: compare in Python
                log.warning("Atlas Vector Search not usable, comparing in Python: %r", exc)
        ids = await self.graph.ids(COLLECTION)
        documents = await asyncio.gather(*[self.graph.get(COLLECTION, i) for i in ids])
        scored = [
            # (1 + cosine) / 2: the same 0-1 scale Atlas Vector Search reports
            (document, (1 + cosine(vector, document["embedding"])) / 2)
            for document in documents
            if document and document.get("embedding")
        ]
        scored.sort(key=lambda pair: -pair[1])
        return scored[:limit]

    async def _atlas_search(self, vector: list[float], limit: int) -> list[tuple[dict, float]]:
        await self.ensure_index()
        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": INDEX,
                    "path": "document.embedding",
                    "queryVector": vector,
                    "numCandidates": max(100, limit * 10),
                    "limit": limit,
                }
            },
            {"$project": {"document": 1, "score": {"$meta": "vectorSearchScore"}}},
        ]
        cursor = await self.graph.database[COLLECTION].aggregate(pipeline)
        rows = [(row["document"], row["score"]) async for row in cursor]
        if not rows:
            raise RuntimeError("the vector index returned nothing (still building?)")
        return rows

    async def ensure_index(self) -> None:
        """Create the Atlas Vector Search index once (cosine over `document.embedding`)."""
        if self._index_checked or not isinstance(self.graph, AtlasGraph):
            return
        self._index_checked = True
        collection = self.graph.database[COLLECTION]
        cursor = await collection.list_search_indexes()
        existing = [index["name"] async for index in cursor]
        if INDEX in existing:
            return
        from pymongo.operations import SearchIndexModel

        definition = {
            "fields": [
                {
                    "type": "vector",
                    "path": "document.embedding",
                    "numDimensions": DIMENSIONS,
                    "similarity": "cosine",
                }
            ]
        }
        model = SearchIndexModel(definition=definition, name=INDEX, type="vectorSearch")
        await collection.create_search_index(model=model)
        log.info("created Atlas Vector Search index %s (it takes about a minute to build)", INDEX)
