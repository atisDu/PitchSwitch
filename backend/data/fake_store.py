"""FakeDataStore: the DataStore contract served from contracts/fixtures/models/ (no network).

B and C develop against this until the real store is ready (gate G2). The data is real Cala data
for the demo cases, recorded by record_fixtures.py and converted by build_fixtures.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from contracts.schemas import Company, EntityRef, PersonLink, PortfolioLink, Reason, Round
from data.config import MODELS_DIR
from data.errors import NotFound
from data.mappers import slug

_REFS = TypeAdapter(list[EntityRef])
_COMPANIES = TypeAdapter(list[Company])
_ROUNDS = TypeAdapter(list[Round])
_PORTFOLIO = TypeAdapter(list[PortfolioLink])
_PEOPLE = TypeAdapter(list[PersonLink])
_REASONS = TypeAdapter(list[Reason])
_CO_INVESTORS = TypeAdapter(list[tuple[EntityRef, int]])

_STOP_WORDS = set("a an and of the in on to for with who what which did do does its it is".split())


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - _STOP_WORDS


class FakeDataStore:
    """Reads fixture files on every call, so a rebuilt fixture shows up without a restart."""

    def __init__(self, models_dir: Path | None = None) -> None:
        self.dir = models_dir or MODELS_DIR

    # --- file access -------------------------------------------------------------------------

    def _read(self, name: str):
        path = self.dir / name
        return json.loads(path.read_text()) if path.exists() else None

    def _index(self) -> dict:
        return self._read("index.json") or {}

    def _canonical(self, entity_id: str) -> str:
        """Cala sometimes has two entries for one firm; fixtures are keyed by the main one."""
        return (self._index().get("aliases") or {}).get(entity_id, entity_id)

    # --- DataStore ---------------------------------------------------------------------------

    async def resolve(self, name: str, kind: Literal["company", "investor"]) -> list[EntityRef]:
        recorded = self._read(f"resolve_{kind}_{slug(name)}.json")
        if recorded is not None:
            return _REFS.validate_python(recorded)
        # Not a recorded search: match the name against every entity in the fixtures.
        wanted = slug(name)
        if not wanted:
            return []
        hits = [
            entity
            for entity in self._index().get("entities") or []
            if entity.get("kind") == kind and wanted in slug(entity.get("name", ""))
        ]
        hits.sort(key=lambda entity: len(entity.get("name", "")))
        return _REFS.validate_python(
            [{k: e.get(k) for k in ("id", "name", "type", "description")} for e in hits]
        )

    async def company(self, id: str) -> Company:
        data = self._read(f"company_{self._canonical(id)}.json")
        if data is None:
            raise NotFound(f"no fixture for company or investor {id}")
        return Company.model_validate(data)

    async def rounds(self, company_id: str) -> list[Round]:
        data = self._read(f"rounds_{self._canonical(company_id)}.json")
        return _ROUNDS.validate_python(data or [])

    async def investor_rounds(self, investor_id: str) -> list[Round]:
        data = self._read(f"investor_rounds_{self._canonical(investor_id)}.json")
        return _ROUNDS.validate_python(data or [])

    async def portfolio(self, investor_id: str) -> list[PortfolioLink]:
        data = self._read(f"portfolio_{self._canonical(investor_id)}.json")
        return _PORTFOLIO.validate_python(data or [])

    async def people(self, company_id: str) -> list[PersonLink]:
        data = self._read(f"people_{self._canonical(company_id)}.json")
        return _PEOPLE.validate_python(data or [])

    async def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]:
        data = self._read(f"candidates_{self._canonical(company.id)}.json")
        return _COMPANIES.validate_python((data or [])[:k])

    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]:
        data = self._read(f"co_investors_{self._canonical(investor_id)}.json")
        return _CO_INVESTORS.validate_python(data or [])

    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]:
        """The recorded answer whose question shares the most words with this one."""
        asked = _words(question)
        best, best_score = None, 0.0
        for entry in self._index().get("sourced_answers") or []:
            recorded = _words(entry.get("question", ""))
            if not recorded or not asked:
                continue
            score = len(asked & recorded) / len(asked | recorded)
            if score > best_score:
                best, best_score = entry, score
        if best is None or best_score < 0.3:
            return "", []
        data = self._read(f"sourced_answer_{best['slug']}.json") or {}
        return data.get("markdown", ""), _REASONS.validate_python(data.get("reasons") or [])
