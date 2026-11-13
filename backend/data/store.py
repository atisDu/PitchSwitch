"""CalaDataStore: the DataStore contract on live Cala data (tasks A6-A12).

One retrieval per entity carries everything we use about it (properties, rounds, investors,
people), so `company()`, `rounds()`, `portfolio()` and `people()` for the same ID share a single
Cala call, and the client's cache makes repeats free. That matters: our key allows about 10
calls a minute.

Cala can hold one firm under two IDs (a Company and an Organization). `resolve()` spots that for
the best match, keeps the entry with more data as the main one and remembers the other as an
alias; the other methods then read both and return everything under the main ID.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from contracts.schemas import Company, EntityRef, PersonLink, PortfolioLink, Reason, Round
from data.cala_client import CalaClient, MemoryCache
from data.errors import NotFound
from data.introspection import fields_for
from data.mappers import (
    ORG_TYPES,
    country_of,
    fill_gaps,
    map_company,
    map_resolve,
    name_key,
)

# What we read about a company or an investor, cut down to what Cala has (introspection map).
_ORG_FIELDS = fields_for("Company", "Organization").only(
    properties=[
        "name",
        "legal_name",
        "aliases",
        "description",
        "website",
        "operational_status",
        "headquarters_address",
        "registered_address",
        "founding_date",
        "funding_stage",
        "total_funding",
        "total_funding_units",
    ],
    outgoing=["PARTICIPATES_IN_FUNDING_ROUND", "INVESTED_IN", "OPERATES_IN_INDUSTRY"],
    incoming=["INVESTED_IN", "IS_BOARD_MEMBER_OF", "FOUNDED", "IS_CEO_OF", "WORKS_AT"],
)
_EDGE_LIMIT = 100
_MAX_SIBLINGS = 3  # entries of one firm we are willing to fetch and compare


def _edge_count(entity: dict) -> int:
    return sum(
        len(items)
        for direction in (entity.get("relationships") or {}).values()
        for items in direction.values()
    )


def _same_firm(a: EntityRef, b: EntityRef) -> bool:
    """Same name once the legal form is dropped, and no sign of different countries."""
    if name_key(a.name) != name_key(b.name):
        return False
    here, there = country_of(None, a.description), country_of(None, b.description)
    return here is None or there is None or here == there


class CalaDataStore:
    def __init__(self, client: CalaClient | None = None) -> None:
        self.cala = client or CalaClient.from_env(cache=MemoryCache())
        self._aliases: dict[str, str] = {}  # other entry of a firm -> its main entry
        self._siblings: dict[str, list[str]] = {}  # main entry -> its other entries

    async def aclose(self) -> None:
        await self.cala.aclose()

    # --- Entities ------------------------------------------------------------------------------

    def canonical(self, entity_id: str) -> str:
        return self._aliases.get(entity_id, entity_id)

    async def _org(self, entity_id: str) -> dict:
        """A company's or investor's retrieval. NotFound if the ID is something else."""
        entity = await self.cala.entity(
            entity_id,
            properties=list(_ORG_FIELDS.properties),
            outgoing=list(_ORG_FIELDS.outgoing),
            incoming=list(_ORG_FIELDS.incoming),
            limit=_EDGE_LIMIT,
        )
        if entity.get("entity_type") not in ORG_TYPES:
            kind = entity.get("entity_type") or "unknown type"
            raise NotFound(f"{entity_id} is not a company or an investor ({kind})")
        return entity

    async def _org_family(self, entity_id: str) -> tuple[str, list[dict]]:
        """The main ID and the retrievals of every entry of that firm, main one first."""
        main_id = self.canonical(entity_id)
        ids = [main_id, *self._siblings.get(main_id, [])]
        entities = await asyncio.gather(*[self._org(i) for i in ids])
        return main_id, list(entities)

    # --- DataStore -----------------------------------------------------------------------------

    async def resolve(self, name: str, kind: Literal["company", "investor"]) -> list[EntityRef]:
        """Companies and organisations matching the name, best first, one entry per firm.

        People, products and places are dropped. For investors, entries that read like an
        investor come first (so "Inflection" does not resolve to Inflection AI).
        """
        if not name.strip():
            return []
        found = await self.cala.search_entities(name, entity_types=sorted(ORG_TYPES), limit=10)
        hits = map_resolve(found, kind, query=name)
        if not hits:
            return []

        # Entries that are the same firm as the best match: fetch them and keep the richest.
        family = [hit for hit in hits if _same_firm(hits[0], hit)][:_MAX_SIBLINGS]
        if len(family) > 1:
            fetched = await asyncio.gather(
                *[self._org(hit.id) for hit in family], return_exceptions=True
            )
            usable = [i for i, entity in enumerate(fetched) if isinstance(entity, dict)]
            family = [family[i] for i in usable]  # an entry we can't read is not merged
            entities = [fetched[i] for i in usable]
        if len(family) > 1:
            order = sorted(
                range(len(family)),
                key=lambda i: (-_edge_count(entities[i]), family[i].type != "Company", i),
            )
            main = family[order[0]]
            others = [family[i] for i in order[1:]]
            if not main.description:
                described = next((o.description for o in others if o.description), None)
                main = main.model_copy(update={"description": described})
            self._siblings[main.id] = [other.id for other in others]
            for other in others:
                self._aliases[other.id] = main.id
            hits = [main, *[hit for hit in hits if hit.id not in {f.id for f in family}]]

        # Further down the list, show one entry per firm without fetching anything.
        seen: list[EntityRef] = []
        for hit in hits:
            if not any(_same_firm(hit, earlier) for earlier in seen):
                seen.append(hit)
        return seen

    async def company(self, id: str) -> Company:
        """A company or an investor. Raises NotFound for an unknown ID."""
        main_id, entities = await self._org_family(id)
        company = map_company(entities[0])
        for other in entities[1:]:
            company = fill_gaps(company, map_company(other))
        return company.model_copy(update={"id": main_id})

    async def rounds(self, company_id: str) -> list[Round]:
        raise NotImplementedError("rounds() arrives with task A7")

    async def investor_rounds(self, investor_id: str) -> list[Round]:
        raise NotImplementedError("investor_rounds() arrives with task A7")

    async def portfolio(self, investor_id: str) -> list[PortfolioLink]:
        raise NotImplementedError("portfolio() arrives with task A8")

    async def people(self, company_id: str) -> list[PersonLink]:
        raise NotImplementedError("people() arrives with task A8")

    async def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]:
        raise NotImplementedError("candidate_competitors() arrives with task A11")

    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]:
        return []  # filled by the batch job (A15); until then nothing is known

    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]:
        raise NotImplementedError("sourced_answer() arrives with task A9")
