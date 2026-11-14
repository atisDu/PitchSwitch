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
import logging
import re
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
from data.cala_client import CalaClient
from data.config import env, env_flag, load_env
from data.errors import NotFound
from data.introspection import fields_for
from data.mappers import (
    ORG_TYPES,
    candidate_rows,
    company_from_row,
    country_of,
    edge_sources,
    fill_gaps,
    looks_like_investor,
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
    row_key,
    stage_index,
    undated_round,
)

log = logging.getLogger("data.store")

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
_ALIASES = "entity_aliases"  # graph collection: other entry's ID -> {"main": EntityRef}
_REGION = ["Finland", "Sweden", "Norway", "Denmark", "Estonia", "Latvia", "Lithuania"]
_PLACE_WORDS = {"finnish", "swedish", "norwegian", "danish", "estonian", "vantaa", "helsinki"}
_REGION_TEXT = "Finland, Sweden, Norway, Denmark, Estonia, Latvia and Lithuania"
_EARLY_STAGES = "Pre-Seed OR Seed OR Series A"
_MAX_NAME_LOOKUPS = 6  # peer rows without an entity that we try to find by name
_VECTOR_NEIGHBOURS = 8  # companies added from vector search when USE_VECTOR_SEARCH is on
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


_INDUSTRY_WORDS = {
    "AEROSPACE_AND_DEFENSE": re.compile(
        r"\b(defen[cs]e|military|drones?|uavs?|uas|aerospace|satellites?|spacecraft|airships?"
        r"|radars?|missiles?)\b"
    ),
}
# Tags too broad to find competitors with ("software" matches every SaaS company).
_BROAD_INDUSTRIES = {"SOFTWARE_AND_SERVICES", "HARDWARE_AND_EQUIPMENT", "CONSULTING", "RETAIL"}
_BOILERPLATE = re.compile(r"\b(founded|headquartered|based|incorporated|registered) (in|at)\b")


def primary_industry(company: Company) -> str | None:
    """The industry tag to look for competitors in.

    A tag the company's own description confirms wins (Stendr: AEROSPACE_AND_DEFENSE, not its
    first tag SOFTWARE_AND_SERVICES). Without tags, the description alone can name it
    (Sensofusion: "defense technology company"). None when nothing points anywhere.
    """
    text = f"{company.name} {company.description or ''}".lower()
    said = [tag for tag, words in _INDUSTRY_WORDS.items() if words.search(text)]
    for tag in said:
        if tag in company.industries:
            return tag
    narrow = [tag for tag in company.industries if tag not in _BROAD_INDUSTRIES]
    if narrow:
        return narrow[0]
    if said:
        return said[0]
    return company.industries[0] if company.industries else None


def industry_queries(company: Company) -> list[tuple[str, str]]:
    """(country, knowledge_query text) pairs: companies of the same industry, per country.

    One query per country: a single query across countries is "too complex" for Cala. The text
    depends only on industry, country and stage group, so companies in the same space share
    cached answers. [] when no industry can be told.
    """
    industry = primary_industry(company)
    if not industry:
        return []
    index = stage_index(company.stage)
    stages = _LATER_STAGES if index is not None and index > 2 else _EARLY_STAGES
    countries = list(_REGION)
    if company.country in countries:  # the company's own country first
        countries.remove(company.country)
        countries.insert(0, company.country)
    return [
        (
            country,
            f"companies.industry={industry}.country={country}.funding_stage={stages}"
            ".return(name, description, funding_stage, total_funding).limit=15",
        )
        for country in countries
    ]


def peers_query(company: Company) -> str:
    """One knowledge_query asking Cala for companies with similar products.

    This finds rivals the industry tags miss (Sensofusion has no tag at all). A description
    is added only when it says what the company does: registry boilerplate ("Finnish company
    founded in 2016 and headquartered in Vantaa") makes Cala's answer worse than the name alone.
    """
    name = re.sub(r"\s+(Oyj?|AB|AS|ASA|ApS|Ltd|GmbH|Inc)\.?$", "", company.name).strip()
    about = (company.description or "").strip().rstrip(".")
    informative = len(about) >= 60 and not _BOILERPLATE.search(about)
    hint = f" ({about})" if informative else ""
    return (
        f"List companies that develop products similar to those of {name}{hint} and compete "
        f"with it, in {_REGION_TEXT}. "
        "Return name, description, country, funding_stage, total_funding."
    )


def _informative(description: str | None) -> int:
    """How much a description says about what a firm does: its length, once registry
    boilerplate (where and when it was founded) is set aside."""
    if not description:
        return 0
    words = re.findall(r"[a-z]+", description.lower())
    filler = {"company", "firm", "founded", "headquartered", "based", "in", "and", "a", "an", "the"}
    return sum(len(word) for word in words if word not in filler and word not in _PLACE_WORDS)


def _same_firm(a: EntityRef, b: EntityRef) -> bool:
    """Same name once the legal form is dropped, and no sign of different countries."""
    if name_key(a.name) != name_key(b.name):
        return False
    here, there = country_of(None, a.description), country_of(None, b.description)
    return here is None or there is None or here == there


def default_client() -> CalaClient:
    """The Cala client for this environment: cached in MongoDB Atlas when MONGODB_URI is set,
    else in local files (.cache/cala/); with CACHE_ONLY=true it answers from the cache and
    never calls Cala."""
    load_env()
    if env("MONGODB_URI"):
        from cache.atlas import AtlasCache

        cache = AtlasCache.from_env()
    else:
        from cache.files import FileCache

        cache = FileCache()
    return CalaClient.from_env(
        cache=cache,
        cache_only=env_flag("CACHE_ONLY"),
        require_cache=env_flag("CALA_REQUIRE_CACHE"),
    )


class CalaDataStore:
    def __init__(self, client: CalaClient | None = None, graph=None) -> None:
        self.cala = client or default_client()
        self._graph = graph  # precomputed investor graph (cache.graph); opened on first use
        self._vectors = None  # company vectors (cache.vector); opened on first use
        self._aliases: dict[str, str] = {}  # other entry of a firm -> its main entry
        self._siblings: dict[str, list[str]] = {}  # main entry -> its other entries
        self._main_refs: dict[str, EntityRef] = {}  # main entry -> how to show it
        self._aliases_loaded = False

    async def aclose(self) -> None:
        await self.cala.aclose()

    # --- Entities ------------------------------------------------------------------------------

    def canonical(self, entity_id: str) -> str:
        """The main ID of the firm this ID belongs to (the ID itself if we know of no other)."""
        for _ in range(5):  # an alias may point at an entry that was folded later
            if entity_id not in self._aliases:
                break
            entity_id = self._aliases[entity_id]
        return entity_id

    def _graph_db(self):
        if self._graph is None:
            from cache.graph import default_graph

            self._graph = default_graph()
        return self._graph

    def _remember(self, other_id: str, main: EntityRef) -> None:
        """Note that `other_id` is another Cala entry of the firm `main`."""
        main_id = self.canonical(main.id)
        if other_id == main_id:
            return
        self._aliases[other_id] = main_id
        self._main_refs.setdefault(main_id, main.model_copy(update={"id": main_id}))
        others = self._siblings.setdefault(main_id, [])
        if other_id not in others:
            others.append(other_id)

    async def _load_aliases(self) -> None:
        """Once per process: read which Cala IDs are the same firm, as found by any teammate's
        process before. This is what makes names and IDs agree across restarts and machines."""
        if self._aliases_loaded:
            return
        self._aliases_loaded = True
        try:
            graph = self._graph_db()
            ids = await graph.ids(_ALIASES)
            documents = await asyncio.gather(*[graph.get(_ALIASES, i) for i in ids])
        except Exception as exc:  # the store works without it, just less consistently
            log.warning("known aliases not readable: %r", exc)
            return
        for other_id, document in zip(ids, documents, strict=True):
            if document and document.get("main"):
                self._remember(other_id, EntityRef.model_validate(document["main"]))

    async def _save_alias(self, other_id: str, main: EntityRef) -> None:
        if self._aliases.get(other_id) == self.canonical(main.id):
            return  # already known
        self._remember(other_id, main)
        try:
            document = {"main": self._main_refs[self.canonical(main.id)].model_dump(mode="json")}
            await self._graph_db().put(_ALIASES, other_id, document)
        except Exception as exc:
            log.warning("alias %s not saved: %r", other_id, exc)

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
        await self._load_aliases()
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
        await self._load_aliases()
        found = await self.cala.search_entities(name, entity_types=sorted(ORG_TYPES), limit=10)
        hits = map_resolve(found, kind, query=name)
        if not hits:
            return []
        # Among equally good matches, a Nordic or Baltic firm first: that is who our users
        # mean (there is a Belgian VC called Inventure as well as the Finnish one).
        wanted = name_key(name)
        hits.sort(
            key=lambda hit: (
                kind == "investor" and not looks_like_investor(hit),
                name_key(hit.name) != wanted,
                name_key(hit.name) == wanted and country_of(None, hit.description) not in _REGION,
            )
        )

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
                key=lambda i: (
                    -_edge_count(entities[i]),
                    -_informative(family[i].description),
                    family[i].type != "Company",
                    i,
                ),
            )
            main = family[order[0]]
            others = [family[i] for i in order[1:]]
            if not main.description:
                described = next((o.description for o in others if o.description), None)
                main = main.model_copy(update={"description": described})
            for other in others:
                await self._save_alias(other.id, main)
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
        mapped = [map_company(entity) for entity in entities]
        company = mapped[0]
        for other in mapped[1:]:
            company = fill_gaps(company, other)
        # Registry entries describe a firm as "Finnish company founded in 2016..."; if another
        # entry of the same firm says what it does, that description is the useful one.
        described = max(mapped, key=lambda c: _informative(c.description))
        if _informative(described.description) > _informative(company.description):
            company = company.model_copy(update={"description": described.description})
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
        # Cala can list one investor under two IDs around the same company, so backers are
        # matched to round investors, and to each other, by name as well as by ID.
        by_name = {name_key(i.investor.name): i.investor.id for r in rounds for i in r.investors}
        in_rounds = set(by_name.values())
        loose: dict[str, EntityRef] = {}
        sources: list[list] = []
        for entity in entities:
            for edge in related(entity, "incoming", "INVESTED_IN"):
                ref = self._ref(edge)
                known_id = by_name.setdefault(name_key(ref.name), ref.id)
                if known_id != ref.id:  # the same investor under another ID
                    main = next(
                        (
                            i.investor
                            for r in rounds
                            for i in r.investors
                            if i.investor.id == known_id
                        ),
                        loose.get(known_id),
                    )
                    if main is not None:
                        await self._save_alias(ref.id, main)
                elif ref.id not in in_rounds and ref.id not in loose:
                    loose[ref.id] = ref
                if known_id in loose:
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
        return self._shown(map_entity_ref(raw))

    def _shown(self, ref: EntityRef) -> EntityRef:
        """`ref` under its firm's main ID and, when it is another entry, the main entry's name."""
        main_id = self.canonical(ref.id)
        if main_id == ref.id:
            return ref
        main = self._main_refs.get(main_id)
        update = {"id": main_id}
        if main is not None:
            update["name"] = main.name
            update["description"] = ref.description or main.description
        return ref.model_copy(update=update)

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
            for item in mapped.investors:  # one entry per firm, under its main ID and name
                ref = self._shown(item.investor)
                main_id = ref.id
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
                    company=self._shown(link.company),
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
        """Companies that may compete with this one, most likely rivals first. Never the
        company itself.

        Two sources, asked in parallel:
        1. Peers: Cala's own list of companies with similar products (one query).
        2. Industry: companies with the same industry tag in each Nordic and Baltic country,
           at early (or later) stages. The tag is the one the description confirms, not just
           the first; own country and nearby stages come first.
        Peers come first. This is a wide net on purpose: judging who is a direct competitor
        is B's step. Candidates come from query rows, so they carry no sources; `company(id)`
        has them.
        """
        await self._load_aliases()
        by_country = industry_queries(company)
        texts = [peers_query(company), *[text for _, text in by_country]]
        answers = await asyncio.gather(
            *[self.cala.query(text) for text in texts], return_exceptions=True
        )
        if all(isinstance(answer, BaseException) for answer in answers):
            raise answers[0]  # Cala is down, not "no competitors"
        answers = [None if isinstance(answer, BaseException) else answer for answer in answers]
        peers, industry = answers[0], answers[1:]

        # Any answer may name an entity that another answer's row lacks.
        known: dict[str, dict] = {}
        for answer in answers:
            for row, entity in candidate_rows(answer):
                if entity:
                    known.setdefault(row_key(str(row["name"])), entity)

        own_ids = {self.canonical(company.id), company.id, *self._siblings.get(company.id, [])}
        own_name = row_key(company.name)
        own_stage = stage_index(company.stage)
        found: dict[str, tuple[tuple, Company]] = {}

        def add(row: dict, entity: dict, rank: tuple, country: str | None = None) -> None:
            candidate = company_from_row(row, entity)
            main_id = self.canonical(candidate.id)
            if main_id in own_ids or main_id in found or row_key(candidate.name) == own_name:
                return
            update: dict = {"id": main_id}
            if not candidate.country and country:
                update["country"] = country
            if main_id in self._main_refs:  # another entry of a known firm: show its main name
                update["name"] = self._main_refs[main_id].name
            found[main_id] = (rank, candidate.model_copy(update=update))

        lookups = 0
        for row_number, (row, entity) in enumerate(candidate_rows(peers)):
            key = row_key(str(row["name"]))
            if key == own_name:
                continue
            entity = entity or known.get(key)
            if entity is None and lookups < _MAX_NAME_LOOKUPS:
                lookups += 1
                entity = await self._find_by_name(str(row["name"]), row.get("country"))
            if entity:
                add(row, entity, (0, row_number))

        for position, ((country, _), answer) in enumerate(zip(by_country, industry, strict=True)):
            for row_number, (row, entity) in enumerate(candidate_rows(answer)):
                if not entity:
                    continue
                stage = stage_index(str(row.get("funding_stage") or ""))
                far_stage = (
                    own_stage is not None and stage is not None and abs(stage - own_stage) > 1
                )
                rank = (1, country != company.country, far_stage, position, row_number)
                add(row, entity, rank, country)

        if env_flag("USE_VECTOR_SEARCH"):
            try:
                await self._add_vector_neighbours(company, found, own_ids, own_name)
            except Exception as exc:  # embeddings or the index failing must not lose a report
                log.warning("vector search skipped for %s: %r", company.name, exc)

        ranked = sorted(found.values(), key=lambda pair: pair[0])
        return [candidate for _, candidate in ranked[: max(k, 0)]]

    async def _add_vector_neighbours(
        self, company: Company, found: dict, own_ids: set[str], own_name: str
    ) -> None:
        """Add the companies closest in meaning to this one (task A13), after the peers and
        before the industry lists. Every candidate found so far is stored with its vector, so
        the pool of known companies grows with each search and one space can feed another."""
        if self._vectors is None:
            from cache.vector import VectorStore

            self._vectors = VectorStore(graph=self._graph_db())
        await self._vectors.upsert([company, *[candidate for _, candidate in found.values()]])
        neighbours = await self._vectors.neighbours(company, k=_VECTOR_NEIGHBOURS + len(own_ids))
        added = 0
        for neighbour, _similarity in neighbours:
            main_id = self.canonical(neighbour.id)
            if main_id in own_ids or main_id in found or row_key(neighbour.name) == own_name:
                continue
            if added >= _VECTOR_NEIGHBOURS:
                break
            found[main_id] = ((0, 1000 + added), neighbour.model_copy(update={"id": main_id}))
            added += 1

    async def _find_by_name(self, name: str, country: object = None) -> dict | None:
        """The Cala entity for a company an answer names without an ID, or None.

        Only an entry with the same name (legal form aside) counts, and not one from another
        country: "Nordic Air Defence" must not become "NORDIC AIR DEFENCE UK LTD".
        """
        wanted = row_key(name)
        try:
            found = await self.cala.search_entities(
                re.sub(r"\([^)]*\)", " ", name).strip(), entity_types=sorted(ORG_TYPES), limit=5
            )
        except Exception as exc:  # a failed lookup just means one candidate fewer
            log.warning("name lookup for %r failed: %r", name, exc)
            return None
        for hit in found.get("entities") or []:
            if hit.get("entity_type") not in ORG_TYPES or row_key(hit.get("name") or "") != wanted:
                continue
            there = country_of(None, hit.get("description"))
            if country and there and str(country) != there:
                continue
            return hit
        return None

    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]:
        """Investors that share companies with this one, with how many, most first.

        Read from the graph the batch job precomputes (`python -m batch.precompute_graph all`).
        [] when the investor has not been crawled yet, or the graph can't be read.
        """
        try:
            await self._load_aliases()
            document = await self._graph_db().get("investor_graph", self.canonical(investor_id))
        except Exception as exc:  # warm paths are a bonus: never fail a report over them
            log.warning("co_investors(%s): graph not readable: %r", investor_id, exc)
            return []
        return [
            (EntityRef.model_validate(row["investor"]), int(row["count"]))
            for row in (document or {}).get("co_investors") or []
        ]

    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]:
        """Cala's own answer to a question (knowledge_search): markdown, plus each claim behind
        it with the documents it rests on. ("", []) for an empty question. Slow: 20-80 s uncached.

        The claims are Cala's wording. Show them as citations as they are; don't rewrite them.
        """
        if not question.strip():
            return "", []
        return map_sourced_answer(await self.cala.search(question.strip()))
