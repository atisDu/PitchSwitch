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

from contracts.schemas import (
    Company,
    EntityRef,
    PersonLink,
    PortfolioLink,
    Reason,
    Round,
    RoundInvestor,
)
from data.cala_client import CalaClient, MemoryCache
from data.config import env, env_flag, load_env
from data.errors import NotFound
from data.introspection import fields_for
from data.mappers import (
    ORG_TYPES,
    country_of,
    edge_sources,
    fill_gaps,
    map_candidate_rows,
    map_company,
    map_entity_ref,
    map_people,
    map_portfolio,
    map_resolve,
    map_round,
    map_sourced_answer,
    merge_sources,
    name_key,
    related,
    stage_index,
    undated_round,
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
_ROUND_FIELDS = fields_for("FundingRound").only(
    properties=[
        "name",
        "round_label",
        "announcement_date",
        "transaction_value",
        "transaction_value_units",
        "instrument",
    ],
    incoming=["PARTICIPATES_IN_FUNDING_ROUND"],
)
_EDGE_LIMIT = 100
_REGION = ["Finland", "Sweden", "Norway", "Denmark", "Estonia", "Latvia", "Lithuania"]
_EARLY_STAGES = "Pre-Seed OR Seed OR Series A"
_LATER_STAGES = "Series A OR Series B OR Series C"
_MAX_INVESTOR_ROUNDS = 40
_MAX_SIBLINGS = 3  # entries of one firm we are willing to fetch and compare


def _edge_count(entity: dict) -> int:
    return sum(
        len(items)
        for direction in (entity.get("relationships") or {}).values()
        for items in direction.values()
    )


def _round_ids(entity: dict, role: str) -> list[str]:
    """IDs of the funding rounds this entity takes part in with the given role."""
    return [
        edge["id"]
        for edge in related(entity, "outgoing", "PARTICIPATES_IN_FUNDING_ROUND")
        if (edge.get("properties") or {}).get("role", role) == role
    ]


def candidate_queries(company: Company) -> list[tuple[str | None, str]]:
    """(country, knowledge_query text) pairs to find competitor candidates.

    One query per country: a single query across countries is "too complex" for Cala. The text
    depends only on industry, country and stage group, so companies in the same space share
    cached answers.
    """
    index = stage_index(company.stage)
    stages = _LATER_STAGES if index is not None and index > 2 else _EARLY_STAGES
    countries = list(_REGION)
    if company.country in countries:  # the company's own country first
        countries.remove(company.country)
        countries.insert(0, company.country)
    if company.industries:
        return [
            (
                country,
                f"companies.industry={company.industries[0]}.country={country}"
                f".funding_stage={stages}"
                ".return(name, description, funding_stage, total_funding).limit=15",
            )
            for country in countries
        ]
    # No industry tag (thin entry): describe the company and let Cala find lookalikes.
    about = (company.description or company.name).strip().rstrip(".")
    where = company.country or "the Nordic and Baltic countries"
    return [
        (
            company.country,
            f"Startups in {where} that compete with this company: {about}. "
            "Return name, description, country, funding stage, total funding",
        )
    ]


def _same_firm(a: EntityRef, b: EntityRef) -> bool:
    """Same name once the legal form is dropped, and no sign of different countries."""
    if name_key(a.name) != name_key(b.name):
        return False
    here, there = country_of(None, a.description), country_of(None, b.description)
    return here is None or there is None or here == there


def default_client() -> CalaClient:
    """The Cala client for this environment: cached in MongoDB Atlas when MONGODB_URI is set,
    else in memory; with CACHE_ONLY=true it answers from the cache and never calls Cala."""
    load_env()
    if env("MONGODB_URI"):
        from cache.atlas import AtlasCache

        cache = AtlasCache.from_env()
    else:
        cache = MemoryCache()
    return CalaClient.from_env(cache=cache, cache_only=env_flag("CACHE_ONLY"))


class CalaDataStore:
    def __init__(self, client: CalaClient | None = None) -> None:
        self.cala = client or default_client()
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
        """The company's funding rounds, newest first. [] for an unknown ID.

        Investors Cala links to the company without round details come last, as one Round
        with no label, date or amount (id "<company_id>:backers").
        """
        try:
            main_id, entities = await self._org_family(company_id)
        except NotFound:
            return []
        rounds = await self._rounds([rid for e in entities for rid in _round_ids(e, "ISSUER")])
        rounds = [r.model_copy(update={"company_id": main_id}) for r in rounds]
        in_rounds = {i.investor.id for r in rounds for i in r.investors}
        loose: dict[str, EntityRef] = {}
        sources: list[list] = []
        for entity in entities:
            for edge in related(entity, "incoming", "INVESTED_IN"):
                ref = self._ref(edge)
                if ref.id not in in_rounds and ref.id not in loose:
                    loose[ref.id] = ref
                    sources.append(edge_sources(edge))
        extra = undated_round(main_id, list(loose.values()), merge_sources(*sources))
        return [*rounds, extra] if extra else rounds

    async def investor_rounds(self, investor_id: str) -> list[Round]:
        """Rounds the investor took part in (up to 40), newest first. [] for an unknown ID."""
        try:
            main_id, entities = await self._org_family(investor_id)
        except NotFound:
            return []
        led: set[str] = set()
        ids: list[str] = []
        for entity in entities:
            for edge in related(entity, "outgoing", "PARTICIPATES_IN_FUNDING_ROUND"):
                properties = edge.get("properties") or {}
                if properties.get("role", "INVESTOR") != "INVESTOR":
                    continue
                ids.append(edge["id"])
                if properties.get("is_lead") is True:
                    led.add(edge["id"])
        rounds = await self._rounds(ids[:_MAX_INVESTOR_ROUNDS])
        result = []
        for item in rounds:
            if item.id in led:  # the investor's own edge says it led this round
                investors = [
                    i.model_copy(update={"is_lead": i.investor.id == main_id})
                    for i in item.investors
                ]
                item = item.model_copy(update={"investors": investors})
            if any(i.investor.id == main_id for i in item.investors):
                result.append(item)
        return result

    def _ref(self, raw: dict) -> EntityRef:
        """An EntityRef for an edge or a search hit, under the firm's main ID."""
        ref = map_entity_ref(raw)
        main_id = self.canonical(ref.id)
        return ref if main_id == ref.id else ref.model_copy(update={"id": main_id})

    async def _rounds(self, round_ids: list[str]) -> list[Round]:
        """Fetch and map funding rounds, newest first. Rounds Cala can't find are skipped."""
        unique = list(dict.fromkeys(round_ids))
        fetched = await asyncio.gather(
            *[
                self.cala.entity(
                    rid,
                    properties=list(_ROUND_FIELDS.properties),
                    incoming=list(_ROUND_FIELDS.incoming),
                    limit=_EDGE_LIMIT,
                )
                for rid in unique
            ],
            return_exceptions=True,
        )
        rounds = []
        for entity in fetched:
            if isinstance(entity, NotFound):
                continue
            if isinstance(entity, BaseException):
                raise entity
            mapped = map_round(entity)
            if mapped is None:
                continue
            investors: dict[str, RoundInvestor] = {}
            for item in mapped.investors:  # one entry per firm, under its main ID
                main_id = self.canonical(item.investor.id)
                ref = item.investor.model_copy(update={"id": main_id})
                previous = investors.get(main_id)
                lead = item.is_lead if previous is None else (previous.is_lead or item.is_lead)
                investors[main_id] = RoundInvestor(investor=ref, is_lead=lead)
            rounds.append(
                mapped.model_copy(
                    update={
                        "company_id": self.canonical(mapped.company_id),
                        "investors": list(investors.values()),
                    }
                )
            )
        return sorted(rounds, key=lambda r: (r.date or "", r.id), reverse=True)

    async def portfolio(self, investor_id: str) -> list[PortfolioLink]:
        """Companies the investor backs (Cala's INVESTED_IN links), by name. [] if unknown.

        The links carry sources but no dates; `investor_rounds()` has the dated deals.
        """
        try:
            main_id, entities = await self._org_family(investor_id)
        except NotFound:
            return []
        links: dict[str, PortfolioLink] = {}
        for entity in entities:
            for link in map_portfolio(entity):
                company_id = self.canonical(link.company.id)
                if company_id == main_id:
                    continue
                previous = links.get(company_id)
                links[company_id] = PortfolioLink(
                    investor_id=main_id,
                    company=link.company.model_copy(update={"id": company_id}),
                    sources=merge_sources(previous.sources if previous else [], link.sources),
                )
        return sorted(links.values(), key=lambda link: link.company.name.lower())

    async def people(self, company_id: str) -> list[PersonLink]:
        """Board members, founders, CEO and employees of a company or an investor.
        [] if Cala lists none or the ID is unknown."""
        try:
            main_id, entities = await self._org_family(company_id)
        except NotFound:
            return []
        people: dict[tuple[str, str], PersonLink] = {}
        for entity in entities:
            for person in map_people(entity):
                key = (person.person.id, person.role)
                previous = people.get(key)
                people[key] = person.model_copy(
                    update={
                        "company_id": main_id,
                        "sources": merge_sources(
                            previous.sources if previous else [], person.sources
                        ),
                    }
                )
        return list(people.values())

    async def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]:
        """Companies that may compete with this one: same industry, in the Nordic and Baltic
        countries, at early (or later) stages. The company itself is left out.

        Ordered by: the company's own country first, then stages next to its own, then Cala's
        order. This is a wide net on purpose; judging who is a direct competitor is B's step.
        Candidates come from query rows, so they carry no sources; `company(id)` has them.
        """
        queries = candidate_queries(company)
        answers = await asyncio.gather(
            *[self.cala.query(text) for _, text in queries], return_exceptions=True
        )
        if answers and all(isinstance(answer, BaseException) for answer in answers):
            raise answers[0]  # Cala is down, not "no competitors"

        own_ids = {self.canonical(company.id), company.id, *self._siblings.get(company.id, [])}
        own_stage = stage_index(company.stage)
        found: dict[str, tuple[tuple, Company]] = {}
        for position, ((country, _), answer) in enumerate(zip(queries, answers, strict=True)):
            if isinstance(answer, BaseException):
                continue  # one country failing should not lose the others
            for row_number, candidate in enumerate(map_candidate_rows(answer)):
                main_id = self.canonical(candidate.id)
                if main_id in own_ids or name_key(candidate.name) == name_key(company.name):
                    continue
                if main_id in found:
                    continue
                if not candidate.country and country:
                    candidate = candidate.model_copy(update={"country": country})
                stage = stage_index(candidate.stage)
                far_stage = (
                    own_stage is not None and stage is not None and abs(stage - own_stage) > 1
                )
                rank = (candidate.country != company.country, far_stage, position, row_number)
                found[main_id] = (rank, candidate.model_copy(update={"id": main_id}))
        ranked = sorted(found.values(), key=lambda pair: pair[0])
        return [candidate for _, candidate in ranked[: max(k, 0)]]

    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]:
        return []  # filled by the batch job (A15); until then nothing is known

    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]:
        """Cala's own answer to a question (knowledge_search): markdown, plus each claim behind
        it with the documents it rests on. ("", []) for an empty question. Slow: 20-80 s uncached.

        The claims are Cala's wording. Show them as citations as they are; don't rewrite them.
        """
        if not question.strip():
            return "", []
        return map_sourced_answer(await self.cala.search(question.strip()))
