"""Walk one company through every DataStore method and print what comes back.

    python -m data.smoke Kelluu            # whatever USE_FAKE_STORE says (fixtures by default)
    python -m data.smoke Kelluu --real     # live Cala (cached; up to 60 calls a minute uncached)

It is the check for gate G2 (real data works end to end) and a way to warm the cache for a
company before a demo. Exit code 0 means every step returned valid contract models.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time


async def walk(name: str, competitors: int) -> int:
    from data import get_store

    store = get_store()
    started = time.monotonic()
    print(f"store: {type(store).__name__}")

    refs = await store.resolve(name, "company")
    print(f"\nresolve({name!r}): {len(refs)} match(es)")
    for ref in refs[:4]:
        print(f"  {ref.id}  {ref.type:12}  {ref.name}")
    if not refs:
        print("nothing to walk")
        return 1

    company = await store.company(refs[0].id)
    print(
        f"\ncompany: {company.name} | {company.stage} | {company.country} | "
        f"{company.total_funding_text} | {company.industries} | {len(company.sources)} sources"
    )

    candidates = await store.candidate_competitors(company)
    print(f"\ncandidate_competitors: {len(candidates)}")
    for candidate in candidates[:12]:
        print(f"  {candidate.name} | {candidate.stage} | {candidate.country}")

    investors: dict[str, str] = {}
    lead: tuple[str, str] | None = None
    print("\nrounds:")
    for target in [company, *candidates[:competitors]]:
        rounds = await store.rounds(target.id)
        print(f"  {target.name}: {len(rounds)} round(s)")
        for item in rounds:
            names = [f"{i.investor.name}{'*' if i.is_lead else ''}" for i in item.investors]
            print(
                f"    {item.label or 'backers (no round details)'} | {item.date} | "
                f"{item.amount_text} | {', '.join(names)} | {len(item.sources)} sources"
            )
            for i in item.investors:
                investors[i.investor.id] = i.investor.name
                if i.is_lead and lead is None:
                    lead = (i.investor.id, i.investor.name)
    print(f"  investors seen: {len(investors)} (* = led the round)")

    if lead is None and investors:
        lead = next(iter(investors.items()))
    if lead:
        investor_id, investor_name = lead
        profile = await store.company(investor_id)
        portfolio = await store.portfolio(investor_id)
        deals = await store.investor_rounds(investor_id)
        people = await store.people(investor_id)
        partners = await store.co_investors(investor_id)
        print(
            f"\ninvestor {investor_name}: {profile.type} | {profile.country} | "
            f"portfolio {len(portfolio)} | rounds {len(deals)} | people {len(people)} | "
            f"co-investors {len(partners)}"
        )
        held = {link.company.id for link in portfolio}
        overlap = [c.name for c in [company, *candidates] if c.id in held]
        print(f"  holds from this space: {overlap}")

    board = await store.people(company.id)
    print(f"\npeople({company.name}): {[(p.person.name, p.role) for p in board][:8]}")

    question = f"Who invested in {name} and who led each of its funding rounds?"
    markdown, reasons = await store.sourced_answer(question)
    cited = sum(len(reason.sources) for reason in reasons)
    print(f"\nsourced_answer: {len(markdown)} chars, {len(reasons)} claims, {cited} sources")
    if reasons:
        print(f"  first claim: {reasons[0].text[:140]}")

    print(f"\ndone in {time.monotonic() - started:.0f} s")
    cala = getattr(store, "cala", None)
    if cala is not None:
        print(f"cala calls: {cala.stats()}")
        await store.aclose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("name", help="company name, e.g. Kelluu")
    parser.add_argument("--real", action="store_true", help="use live Cala (USE_FAKE_STORE=false)")
    parser.add_argument(
        "--competitors", type=int, default=4, help="candidates whose rounds to read"
    )
    parser.add_argument("--verbose", action="store_true", help="log every Cala call")
    args = parser.parse_args()
    if args.real:
        os.environ["USE_FAKE_STORE"] = "false"
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return asyncio.run(walk(args.name, args.competitors))


if __name__ == "__main__":
    raise SystemExit(main())
