"""Shared test helpers for the data layer."""

import json

import pytest

from data.config import RAW_DIR
from data.errors import NotFound
from data.mappers import slug


class RecordedCala:
    """Stands in for CalaClient: answers from contracts/fixtures/raw/, never the network."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    @staticmethod
    def _load(kind: str, key: str):
        path = RAW_DIR / kind / f"{key}.json"
        return json.loads(path.read_text())["response"] if path.exists() else None

    @staticmethod
    def _by_input(kind: str, text: str):
        for path in sorted((RAW_DIR / kind).glob("*.json")):
            envelope = json.loads(path.read_text())
            if envelope["request"]["json"]["input"] == text:
                return envelope["response"]
        return None

    async def search_entities(self, name, entity_types=None, limit=10):
        self.calls.append(("search_entities", name))
        found = self._load("entity_search", slug(name)) or {"entities": []}
        hits = [
            hit
            for hit in found["entities"]
            if not entity_types or hit.get("entity_type") in entity_types
        ]
        return {"entities": hits[:limit]}

    async def entity(self, entity_id, **projection):
        self.calls.append(("entity", entity_id))
        found = self._load("entity", entity_id)
        if found is None:
            raise NotFound(f"no recording for {entity_id}")
        return found

    async def query(self, text):
        self.calls.append(("query", text))
        return self._by_input("knowledge_query", text) or {"results": [], "entities": []}

    async def search(self, text):
        self.calls.append(("search", text))
        return self._by_input("knowledge_search", text) or {
            "content": "",
            "explainability": [],
            "context": [],
            "entities": [],
        }

    async def aclose(self):
        pass


@pytest.fixture
def cala():
    return RecordedCala()


@pytest.fixture
def cases():
    """The demo cases and their Cala IDs (raw/manifest.json)."""
    return json.loads((RAW_DIR / "manifest.json").read_text())
