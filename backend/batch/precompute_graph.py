"""Precompute the investor graph (tasks A14 crawl, A15 derive). Runs as a batch job.

    python -m batch.precompute_graph crawl     # part 1: fetch investors, portfolios and rounds
    python -m batch.precompute_graph derive    # part 2: co-investor counts and activity stats
    python -m batch.precompute_graph all

Part 1 finds the investors that matter for our demo space, then reads each one's profile,
portfolio and funding rounds from Cala through the data store. Every Cala response lands in the
shared cache, so the app answers instantly for these investors afterwards, and one summary
document per investor is written to the `crawl_investors` collection for part 2.

The job is safe to stop and rerun: an investor crawled in the last 24 hours is skipped, and
Cala calls already made come from the cache. Cala allows about 10 calls a minute on our key, so
expect roughly 5-10 investors a minute at best.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from cache.graph import GraphDB, default_graph
from contracts.schemas import DataStore, EntityRef
from data.errors import DataError
from data.mappers import ORG_TYPES, looks_like_investor, map_entity_ref, name_key

log = logging.getLogger("batch.graph")

CRAWLED = "crawl_investors"
GRAPH = "investor_graph"
ACTIVITY = "investor_activity"
MAX_CO_INVESTORS = 50
FRESH_FOR = 24 * 60 * 60

# Companies whose space we care about first (the demo cases).
SEEDS = ["Kelluu", "Sensofusion", "Stendr", "NestAI"]
COUNTRIES = ["Finland", "Sweden", "Norway", "Denmark", "Estonia", "Latvia", "Lithuania"]
_INVESTOR_QUESTION = (
    "Venture capital firms and other startup investors based in {country} that invested in "
    "startups since 2024: name, description"
)


async def investors_from_seeds(
    store: DataStore, seeds: list[str], per_seed: int = 30
) -> dict[str, EntityRef]:
    """Investors behind each seed company and its competitor candidates."""
    found: dict[str, EntityRef] = {}
    for seed in seeds:
        try:
            matches = await store.resolve(seed, "company")
            if not matches:
                log.warning("seed %s: not found in Cala", seed)
                continue
            company = await store.company(matches[0].id)
            candidates = await store.candidate_competitors(company, k=per_seed)
            before = len(found)
            for target in [company, *candidates]:
                for item in await store.rounds(target.id):
                    for investor in item.investors:
                        found.setdefault(investor.investor.id, investor.investor)
            log.info(
                "seed %s: %d candidates, %d new investors",
                company.name,
                len(candidates),
                len(found) - before,
            )
        except DataError as exc:
            log.warning("seed %s failed, continuing: %s", seed, exc)
    return found


async def investors_by_country(cala, countries: list[str]) -> dict[str, EntityRef]:
    """Active investors per country, from one knowledge_query each."""
    found: dict[str, EntityRef] = {}
    for country in countries:
        try:
            answer = await cala.query(_INVESTOR_QUESTION.format(country=country))
        except DataError as exc:
            log.warning("investor list for %s failed, continuing: %s", country, exc)
            continue
        names = {
            name_key(str(row["name"]))
            for row in answer.get("results") or []
            if isinstance(row, dict) and row.get("name")
        }
        before = len(found)
        for entity in answer.get("entities") or []:
            if entity.get("entity_type") not in ORG_TYPES:
                continue
            mentions = entity.get("mentions") or []
            labels = {name_key(text) for text in [entity.get("name") or "", *mentions]}
            if labels & names:
                found.setdefault(entity["id"], map_entity_ref(entity))
        log.info("investors in %s: %d new", country, len(found) - before)
    return found


async def crawl_investor(
    store: DataStore, graph: GraphDB, ref: EntityRef, *, now: float, force: bool = False
) -> str:
    """Fetch one investor and store its summary. Returns "crawled", "skipped" or "failed"."""
    previous = await graph.get(CRAWLED, ref.id)
    if previous and not force and not previous.get("error"):
        if now - previous.get("crawled_at", 0) < FRESH_FOR:
            return "skipped"
    try:
        profile = await store.company(ref.id)
        portfolio = await store.portfolio(ref.id)
        rounds = await store.investor_rounds(ref.id)
    except DataError as exc:
        log.warning("investor %s failed: %s", ref.name, exc)
        await graph.put(CRAWLED, ref.id, {"name": ref.name, "error": str(exc), "crawled_at": now})
        return "failed"
    await graph.put(
        CRAWLED,
        profile.id,
        {
            "name": profile.name,
            "investor": profile.model_dump(mode="json"),
            "portfolio": [link.model_dump(mode="json") for link in portfolio],
            "rounds": [item.model_dump(mode="json") for item in rounds],
            "crawled_at": now,
        },
    )
    log.info("investor %s: %d companies, %d rounds", profile.name, len(portfolio), len(rounds))
    return "crawled"


async def crawl(
    store: DataStore,
    graph: GraphDB,
    *,
    seeds: list[str] | None = None,
    countries: list[str] | None = None,
    max_investors: int = 150,
    force: bool = False,
    clock: Callable[[], float] = time.time,
) -> dict:
    """Part 1. Returns counts: {"found", "crawled", "skipped", "failed"}."""
    seeds = SEEDS if seeds is None else seeds
    countries = COUNTRIES if countries is None else countries

    investors = await investors_from_seeds(store, seeds)  # the demo space first
    cala = getattr(store, "cala", None)
    if cala is not None and countries:
        for investor_id, ref in (await investors_by_country(cala, countries)).items():
            investors.setdefault(investor_id, ref)

    # Entries that read like investors first; a person or a corporate backer can wait.
    queue = sorted(investors.values(), key=lambda ref: not looks_like_investor(ref))
    queue = queue[: max(max_investors, 0)]
    counts = {"found": len(investors), "crawled": 0, "skipped": 0, "failed": 0}
    for position, ref in enumerate(queue, start=1):
        outcome = await crawl_investor(store, graph, ref, now=clock(), force=force)
        counts[outcome] += 1
        if position % 10 == 0 or position == len(queue):
            log.info("progress: %d/%d investors (%s)", position, len(queue), counts)
    return counts


async def derive(graph: GraphDB, *, clock: Callable[[], float] = time.time) -> dict:
    """Part 2. From the crawled investors, write per investor:

    investor_graph     {investor, co_investors: [{investor, count}]}  count = companies shared
    investor_activity  {investor, last_lead_date, last_deal_date, deals_last_12m, leads_total,
                        rounds_total, companies_total, rounds_by_stage}

    Returns counts: {"investors", "with_co_investors"}.
    """
    now = clock()
    year_ago = (datetime.fromtimestamp(now, UTC) - timedelta(days=365)).date().isoformat()
    documents = {}
    for investor_id in await graph.ids(CRAWLED):
        document = await graph.get(CRAWLED, investor_id)
        if document and not document.get("error"):
            documents[investor_id] = document

    # One ID per investor name: a crawled entry wins over one only seen in somebody's round.
    main_by_name = {name_key(doc["name"]): investor_id for investor_id, doc in documents.items()}
    refs: dict[str, dict] = {}
    held: dict[str, set[str]] = defaultdict(set)  # investor -> companies it is tied to

    def main_id(ref: dict) -> str:
        found = main_by_name.setdefault(name_key(ref["name"]), ref["id"])
        refs.setdefault(found, {**ref, "id": found})
        return found

    rounds_of: dict[str, dict[str, dict]] = defaultdict(dict)  # investor -> round id -> round
    for investor_id, document in documents.items():
        profile = document["investor"]
        ref = {key: profile.get(key) for key in ("id", "name", "type", "description")}
        refs[investor_id] = {**ref, "id": investor_id}
        for link in document["portfolio"]:
            held[investor_id].add(link["company"]["id"])
        for item in document["rounds"]:
            for participant in item["investors"]:
                other = main_id(participant["investor"])
                held[other].add(item["company_id"])
                rounds_of[other][item["id"]] = {**item, "_lead": participant.get("is_lead")}

    counts = {"investors": len(documents), "with_co_investors": 0}
    for investor_id in documents:
        mine = held.get(investor_id, set())  # .get: an investor with nothing must not add a key
        partners = [
            {"investor": refs[other], "count": len(mine & companies)}
            for other, companies in held.items()
            if other != investor_id and mine & companies
        ]
        partners.sort(key=lambda p: (-p["count"], p["investor"]["name"].lower()))
        counts["with_co_investors"] += bool(partners)
        await graph.put(
            GRAPH,
            investor_id,
            {
                "investor": refs[investor_id],
                "co_investors": partners[:MAX_CO_INVESTORS],
                "derived_at": now,
            },
        )

        deals = list(rounds_of.get(investor_id, {}).values())
        dated = sorted(item["date"] for item in deals if item.get("date"))
        led = sorted(item["date"] for item in deals if item["_lead"] is True and item.get("date"))
        stages = Counter(item.get("label") or "Unknown" for item in deals)
        await graph.put(
            ACTIVITY,
            investor_id,
            {
                "investor": refs[investor_id],
                "last_lead_date": led[-1] if led else None,
                "last_deal_date": dated[-1] if dated else None,
                "deals_last_12m": sum(day >= year_ago for day in dated),
                "leads_total": sum(item["_lead"] is True for item in deals),
                "rounds_total": len(deals),
                "companies_total": len(mine),
                "rounds_by_stage": dict(sorted(stages.items())),
                "derived_at": now,
            },
        )
    return counts


async def _run(args: argparse.Namespace) -> int:
    graph = default_graph()
    log.info("graph: %s", type(graph).__name__)
    store = None
    try:
        if args.step in ("crawl", "all"):
            os.environ["USE_FAKE_STORE"] = "false"  # a crawl is only useful on live data
            from data import get_store

            store = get_store()
            if args.per_minute:
                store.cala.per_minute = args.per_minute  # leave room for teammates on the key
            counts = await crawl(
                store,
                graph,
                seeds=args.seeds.split(",") if args.seeds else None,
                countries=[] if args.no_countries else None,
                max_investors=args.max_investors,
                force=args.force,
            )
            log.info("crawl done: %s", counts)
            log.info("cala calls: %s", store.cala.stats())
        if args.step in ("derive", "all"):
            log.info("derive done: %s", await derive(graph))
    finally:
        if store is not None:
            await store.aclose()
        if hasattr(graph, "aclose"):
            await graph.aclose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=["crawl", "derive", "all"])
    parser.add_argument("--seeds", help="comma-separated company names (default: the demo cases)")
    parser.add_argument("--no-countries", action="store_true", help="skip the per-country lists")
    parser.add_argument("--max-investors", type=int, default=150)
    parser.add_argument("--force", action="store_true", help="re-crawl fresh investors too")
    parser.add_argument(
        "--per-minute", type=int, default=0, help="Cala calls a minute (default: the client's 10)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("data.cala").setLevel(logging.WARNING)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
