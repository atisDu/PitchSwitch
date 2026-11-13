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
from collections.abc import Callable

from cache.graph import GraphDB, default_graph
from contracts.schemas import DataStore, EntityRef
from data.errors import DataError
from data.mappers import ORG_TYPES, looks_like_investor, map_entity_ref, name_key

log = logging.getLogger("batch.graph")

CRAWLED = "crawl_investors"
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


async def _run(args: argparse.Namespace) -> int:
    os.environ["USE_FAKE_STORE"] = "false"  # a batch job is only useful on live data
    from data import get_store

    store = get_store()
    graph = default_graph()
    log.info("store: %s, graph: %s", type(store).__name__, type(graph).__name__)
    try:
        if args.step in ("crawl", "all"):
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
            log.error("derive is task A15 and is not built yet")
            return 2 if args.step == "derive" else 0
    finally:
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("data.cala").setLevel(logging.WARNING)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
