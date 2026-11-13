"""Build contract-model fixtures from the raw Cala recordings (task A2).

    python -m data.build_fixtures

Reads contracts/fixtures/raw/ (written by record_fixtures.py) and rewrites
contracts/fixtures/models/ from scratch. The output only depends on raw/, so running it twice
gives the same files. The file list is in contracts/api.md -> Fixtures.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from contracts.schemas import (
    CONTRACT_VERSION,
    Company,
    EntityRef,
    PersonLink,
    PortfolioLink,
    Round,
    RoundInvestor,
)
from data.config import MODELS_DIR, RAW_DIR
from data.mappers import (
    ORG_TYPES,
    fill_gaps,
    looks_like_investor,
    map_backers,
    map_candidate_rows,
    map_company,
    map_entity_ref,
    map_people,
    map_portfolio,
    map_resolve,
    map_round,
    map_sourced_answer,
    merge_sources,
    related,
    slug,
    undated_round,
)

MAX_CANDIDATES = 30
MAX_CO_INVESTORS = 50

# Which demo cases get sample API responses (contracts/fixtures/README.md).
# Nordic Air Defence has no company entity in Cala, so Stendr stands in as the third company.
FOUNDER_MODE = ["kelluu", "sensofusion", "stendr"]
INVESTOR_MODE = [("tesi", "nestai"), ("maki-vc", "stendr")]


class Graph:
    """Everything the raw recordings say, as contract models keyed by canonical Cala ID."""

    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = raw_dir
        self.manifest = self._load("manifest.json") or {}
        self.cases = {
            "company": self.manifest.get("companies") or {},
            "investor": self.manifest.get("investors") or {},
        }
        self.aliases: dict[str, str] = {}
        for group in self.cases.values():
            for case in group.values():
                for alt in case.get("alt") or []:
                    if case.get("id"):
                        self.aliases[alt] = case["id"]
        self.recorded_on = ""

        self.raw_entities: dict[str, dict] = {}
        for file in sorted((raw_dir / "entity").glob("*.json")):
            envelope = json.loads(file.read_text())
            self.raw_entities[file.stem] = envelope["response"]
            self.recorded_on = max(self.recorded_on, envelope.get("recorded_at", "")[:10])

        self._alias_same_names()

        self.companies: dict[str, Company] = {}
        self.refs: dict[str, EntityRef] = {}
        self.rounds: dict[str, Round] = {}
        self.links: dict[str, dict[str, PortfolioLink]] = defaultdict(dict)  # investor -> company
        self.people: dict[str, list[PersonLink]] = defaultdict(list)
        self._build()

    def _alias_same_names(self) -> None:
        """Cala can hold one firm under several IDs (a Company and an Organization, or one entry
        per data source). Entries with the same name are folded into one: a pinned demo case
        first, else the entry we recorded in full with the most edges."""
        pinned = {c["id"] for group in self.cases.values() for c in group.values() if c.get("id")}
        by_name: dict[str, set[str]] = defaultdict(set)
        for entity in self.raw_entities.values():
            edges = [
                edge
                for direction in (entity.get("relationships") or {}).values()
                for items in direction.values()
                for edge in items
            ]
            for item in [entity, *edges]:
                if item.get("entity_type") in ORG_TYPES and item.get("name") and item.get("id"):
                    by_name[slug(item["name"])].add(self.canon(item["id"]))

        def weight(entity_id: str) -> tuple:
            entity = self.raw_entities.get(entity_id) or {}
            edges = sum(
                len(items)
                for direction in (entity.get("relationships") or {}).values()
                for items in direction.values()
            )
            return (entity_id not in pinned, entity_id not in self.raw_entities, -edges, entity_id)

        for ids in by_name.values():
            if len(ids) > 1:
                main, *others = sorted(ids, key=weight)
                for other in others:
                    self.aliases[other] = main
        for alias, main in list(self.aliases.items()):  # an alias of an alias points at the end
            self.aliases[alias] = self.aliases.get(main, main)

    def _load(self, name: str):
        path = self.raw_dir / name
        return json.loads(path.read_text()) if path.exists() else None

    def canon(self, entity_id: str) -> str:
        return self.aliases.get(entity_id, entity_id)

    def ref(self, raw: EntityRef) -> EntityRef:
        """The best-known EntityRef for this entity (canonical ID, description if we have one)."""
        entity_id = self.canon(raw.id)
        known = self.refs.get(entity_id)
        if known is None:
            known = raw.model_copy(update={"id": entity_id})
            self.refs[entity_id] = known
        elif not known.description and raw.description:
            known = known.model_copy(update={"description": raw.description})
            self.refs[entity_id] = known
        return known

    def _build(self) -> None:
        orgs = {i: e for i, e in self.raw_entities.items() if e.get("entity_type") in ORG_TYPES}
        rounds = {
            i: e for i, e in self.raw_entities.items() if e.get("entity_type") == "FundingRound"
        }

        # Companies and investors. An alias entry only fills gaps in its main entry.
        for entity_id in sorted(orgs, key=lambda i: (i in self.aliases, i)):
            company = map_company(orgs[entity_id])
            main_id = self.canon(entity_id)
            if main_id in self.companies:
                company = fill_gaps(self.companies[main_id], company)
            self.companies[main_id] = company.model_copy(update={"id": main_id})
        for entity_id, company in self.companies.items():
            self.refs[entity_id] = EntityRef(
                id=entity_id, name=company.name, type=company.type, description=company.description
            )

        # Funding rounds.
        for entity_id in sorted(rounds):
            mapped = map_round(rounds[entity_id])
            if mapped is None:
                continue
            investors: dict[str, RoundInvestor] = {}
            for item in mapped.investors:
                ref = self.ref(item.investor)
                previous = investors.get(ref.id)
                lead = item.is_lead if previous is None else (previous.is_lead or item.is_lead)
                investors[ref.id] = RoundInvestor(investor=ref, is_lead=lead)
            self.rounds[entity_id] = mapped.model_copy(
                update={
                    "company_id": self.canon(mapped.company_id),
                    "investors": list(investors.values()),
                }
            )

        # Who invested in what: investor portfolios, company backers, round participants.
        for entity_id in sorted(orgs):
            for edge in related(orgs[entity_id], "incoming", "INVESTED_IN"):
                self.ref(map_entity_ref(edge))  # remember the backer's name
            for link in [*map_portfolio(orgs[entity_id]), *map_backers(orgs[entity_id])]:
                self._add_link(link)
            for person in map_people(orgs[entity_id]):
                main_id = self.canon(entity_id)
                if not any(
                    p.person.id == person.person.id and p.role == person.role
                    for p in self.people[main_id]
                ):
                    self.people[main_id].append(person.model_copy(update={"company_id": main_id}))
        for item in self.rounds.values():
            issuer = self.refs.get(item.company_id)
            if issuer is None:
                issuer = self._issuer_ref(item)
            for investor in item.investors:
                self._add_link(
                    PortfolioLink(
                        investor_id=investor.investor.id, company=issuer, sources=item.sources
                    )
                )

    def _issuer_ref(self, item: Round) -> EntityRef:
        raw = self.raw_entities[item.id]
        for edge in (
            (raw.get("relationships") or {})
            .get("incoming", {})
            .get("PARTICIPATES_IN_FUNDING_ROUND", [])
        ):
            if self.canon(edge["id"]) == item.company_id:
                return self.ref(map_entity_ref(edge))
        return self.ref(EntityRef(id=item.company_id, name=item.company_id, type="Company"))

    def _add_link(self, link: PortfolioLink) -> None:
        investor_id = self.canon(link.investor_id)
        company = self.ref(link.company)
        if investor_id == company.id:
            return
        previous = self.links[investor_id].get(company.id)
        sources = merge_sources(previous.sources if previous else [], link.sources)
        self.links[investor_id][company.id] = PortfolioLink(
            investor_id=investor_id, company=company, sources=sources
        )

    # --- Views ---------------------------------------------------------------------------------

    def rounds_of(self, company_id: str) -> list[Round]:
        """The company's rounds, newest first, then its backers that appear in no round."""
        rounds = _newest_first(r for r in self.rounds.values() if r.company_id == company_id)
        in_rounds = {i.investor.id for r in rounds for i in r.investors}
        loose = [link for link in self.backers(company_id) if link.investor_id not in in_rounds]
        extra = undated_round(
            company_id,
            [self.refs[link.investor_id] for link in loose if link.investor_id in self.refs],
            merge_sources(*[link.sources for link in loose]),
        )
        return [*rounds, extra] if extra else rounds

    def investor_rounds(self, investor_id: str) -> list[Round]:
        return _newest_first(
            r
            for r in self.rounds.values()
            if any(i.investor.id == investor_id for i in r.investors)
        )

    def portfolio(self, investor_id: str) -> list[PortfolioLink]:
        return sorted(
            self.links.get(investor_id, {}).values(), key=lambda link: link.company.name.lower()
        )

    def backers(self, company_id: str) -> list[PortfolioLink]:
        found = [links[company_id] for links in self.links.values() if company_id in links]
        return sorted(found, key=lambda link: self.name(link.investor_id).lower())

    def investor_ids(self) -> list[str]:
        return sorted(self.links)

    def name(self, entity_id: str) -> str:
        ref = self.refs.get(entity_id)
        return ref.name if ref else entity_id

    def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]:
        """Other investors behind the same companies, with how many companies they share."""
        mine = set(self.links.get(investor_id, {}))
        counts = []
        for other, links in self.links.items():
            shared = len(mine & set(links))
            if other != investor_id and shared and other in self.refs:
                counts.append((self.refs[other], shared))
        counts.sort(key=lambda pair: (-pair[1], pair[0].name.lower()))
        return counts[:MAX_CO_INVESTORS]

    def candidate_pool(self) -> list[Company]:
        """Companies a founder-mode company could compete with: the demo companies plus the
        candidates Cala returned for the same industry, region and stage."""
        pool: dict[str, Company] = {}
        for case in self.cases["company"].values():
            if case.get("id") and case["id"] in self.companies:
                pool[case["id"]] = self.companies[case["id"]]
        for entity_id in self.manifest.get("candidate_company_ids") or []:
            main_id = self.canon(entity_id)
            if main_id in self.companies:
                pool.setdefault(main_id, self.companies[main_id])
        for file in sorted((self.raw_dir / "knowledge_query").glob("*.json")):
            for row in map_candidate_rows(json.loads(file.read_text())["response"]):
                main_id = self.canon(row.id)
                if main_id in pool:
                    pool[main_id] = fill_gaps(pool[main_id], row)
                    self.companies[main_id] = pool[main_id]  # company() agrees with candidates
                else:
                    pool[main_id] = row.model_copy(update={"id": main_id})
        return list(pool.values())


def _newest_first(rounds) -> list[Round]:
    return sorted(rounds, key=lambda r: (r.date or "", r.id), reverse=True)


def _dump(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list | tuple):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    return value


class Writer:
    def __init__(self, models_dir: Path) -> None:
        self.dir = models_dir
        self.files: list[str] = []

    def write(self, name: str, value) -> None:
        text = json.dumps(_dump(value), indent=1, ensure_ascii=False) + "\n"
        (self.dir / name).write_text(text)
        self.files.append(name)


def build(raw_dir: Path = RAW_DIR, models_dir: Path = MODELS_DIR) -> dict:
    """Rewrite models_dir from raw_dir. Returns the index (also written as index.json)."""
    from data.sample_responses import write_samples  # samples need the graph; avoid a cycle

    graph = Graph(raw_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    for old in models_dir.glob("*.json"):
        old.unlink()
    out = Writer(models_dir)
    pool = graph.candidate_pool()  # first: it also fills gaps in the companies

    for entity_id, company in sorted(graph.companies.items()):
        out.write(f"company_{entity_id}.json", company)
        if rounds := graph.rounds_of(entity_id):
            out.write(f"rounds_{entity_id}.json", rounds)
        if people := graph.people.get(entity_id):
            out.write(f"people_{entity_id}.json", people)
    for investor_id in graph.investor_ids():
        out.write(f"portfolio_{investor_id}.json", graph.portfolio(investor_id))
        if rounds := graph.investor_rounds(investor_id):
            out.write(f"investor_rounds_{investor_id}.json", rounds)
        if partners := graph.co_investors(investor_id):
            out.write(f"co_investors_{investor_id}.json", partners)

    for case in graph.cases["company"].values():
        if case.get("id"):
            candidates = [c for c in pool if c.id != case["id"]][:MAX_CANDIDATES]
            out.write(f"candidates_{case['id']}.json", candidates)

    answers = []
    for key, question in sorted((graph.manifest.get("questions") or {}).items()):
        path = raw_dir / "knowledge_search" / f"{key}.json"
        if not path.exists():
            continue
        markdown, reasons = map_sourced_answer(json.loads(path.read_text())["response"])
        out.write(
            f"sourced_answer_{key}.json",
            {"question": question, "markdown": markdown, "reasons": reasons},
        )
        answers.append({"slug": key, "question": question})

    for kind, group in graph.cases.items():
        for case in group.values():
            path = raw_dir / "entity_search" / f"{slug(case['name'])}.json"
            if not path.exists():
                continue
            hits = map_resolve(json.loads(path.read_text())["response"], kind, query=case["name"])
            refs: dict[str, EntityRef] = {}
            if case.get("id") and case["id"] in graph.refs:  # the pinned entry comes first
                refs[case["id"]] = graph.refs[case["id"]]
            for hit in hits:
                main_id = graph.canon(hit.id)
                refs.setdefault(main_id, graph.refs.get(main_id) or hit)
            out.write(f"resolve_{kind}_{slug(case['name'])}.json", list(refs.values()))

    samples = write_samples(graph, out, pool, FOUNDER_MODE, INVESTOR_MODE)

    def kind_of(entity_id: str) -> str:
        ref = graph.refs[entity_id]
        return "investor" if entity_id in graph.links or looks_like_investor(ref) else "company"

    index = {
        "contract_version": CONTRACT_VERSION,
        "recorded_on": graph.recorded_on,
        "note": "Built by backend/data/build_fixtures.py from raw/. Do not edit by hand.",
        "companies": {
            key: {"id": case.get("id"), "name": case["name"], "alt_ids": case.get("alt") or []}
            for key, case in graph.cases["company"].items()
        },
        "investors": {
            key: {"id": case.get("id"), "name": case["name"], "alt_ids": case.get("alt") or []}
            for key, case in graph.cases["investor"].items()
        },
        "aliases": dict(sorted(graph.aliases.items())),
        **samples,
        "sourced_answers": answers,
        "entities": [
            {**_dump(graph.refs[entity_id]), "kind": kind_of(entity_id)}
            for entity_id in sorted(graph.refs, key=lambda i: graph.refs[i].name.lower())
            if graph.refs[entity_id].type in ORG_TYPES
        ],
        "files": sorted(out.files),
    }
    out.write("index.json", index)
    return index


def main() -> int:
    index = build()
    print(f"wrote {len(index['files']) + 1} files to {MODELS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
