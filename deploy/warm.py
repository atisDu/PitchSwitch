"""Warm the cache for the demo, and check that the demo path answers fast (task A18).

    python deploy/warm.py                                   # the deployed site
    python deploy/warm.py --base http://localhost:8000      # a local backend
    python deploy/warm.py --check                           # second pass: fail if anything is slow

It calls the public API the way the frontend does, for every page the demo can reach:
the founder report of each demo company, then the investor check and the brief for the
investors a presenter might click (top of Pitch, all of Skip), plus the two investor-mode pairs.
Everything it touches lands in the shared Atlas cache. The first pass can take many minutes
(Cala allows about 10 calls a minute); a second pass should take seconds per page.

With --check, any failed or slow call makes the exit code 1. Run it with CACHE_ONLY=true on the
server to prove the demo needs no live Cala call.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://95-133-252-219.sslip.io"
FOUNDER_COMPANIES = [
    "Sensofusion",
    "Stendr",
    "Kelluu",
]  # the demo is Sensofusion; the rest back it up
INVESTOR_PAIRS = [("Tesi", "NestAI"), ("Maki.vc", "Stendr")]
TOP_PITCH = 3  # investors from the top of each Pitch list to warm
MAX_SKIP = 6  # investors from each Skip list to warm


class Run:
    def __init__(self, base: str, slow: float) -> None:
        self.base = base.rstrip("/")
        self.slow = slow
        self.rows: list[tuple[str, int, float]] = []

    def post(self, label: str, path: str, body: dict):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "pitchlist-warm",
            },
            method="POST",
        )
        started = time.monotonic()
        status, payload = 0, None
        try:
            with urllib.request.urlopen(request, timeout=1800) as reply:
                status, payload = reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            status = error.code
            payload = error.read().decode(errors="replace")[:200]
        except (OSError, ValueError) as error:  # timeout, connection refused, bad JSON
            payload = repr(error)[:200]
        seconds = time.monotonic() - started
        self.rows.append((label, status, seconds))
        note = "" if status == 200 else f"  <- {payload}"
        flag = "  SLOW" if status == 200 and seconds > self.slow else ""
        print(f"{status or 'ERR':>4} {seconds:7.1f}s  {label}{flag}{note}", flush=True)
        return payload if status == 200 else None

    def resolve(self, name: str, kind: str) -> dict | None:
        found = self.post(
            f"resolve {kind} {name}", "/api/resolve", {"name": name, "kind": kind}
        )
        return found[0] if found else None

    def investor_pages(self, investor: dict, company: dict) -> None:
        ids = {"investor_id": investor["id"], "company_id": company["id"]}
        self.post(
            f"  check  {investor['name']} x {company['name']}",
            "/api/investor/check",
            ids,
        )
        self.post(f"  brief  {investor['name']} x {company['name']}", "/api/brief", ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if a call fails or is slow"
    )
    parser.add_argument(
        "--slow", type=float, default=15.0, help="seconds that count as slow"
    )
    args = parser.parse_args()
    run = Run(args.base, args.slow)
    print(f"warming {run.base}")

    for name in FOUNDER_COMPANIES:
        company = run.resolve(name, "company")
        if not company:
            continue
        body = {"company_id": company["id"]}
        report = run.post(
            f"founder report {company['name']}", "/api/founder/analyze", body
        )
        if not report:
            continue
        shown = [*report["pitch"][:TOP_PITCH], *report["skip"][:MAX_SKIP]]
        for score in shown:
            run.investor_pages(score["investor"], report["company"])

    for investor_name, company_name in INVESTOR_PAIRS:
        investor = run.resolve(investor_name, "investor")
        company = run.resolve(company_name, "company")
        if investor and company:
            run.investor_pages(investor, company)

    failed = [row for row in run.rows if row[1] != 200]
    slow = [row for row in run.rows if row[1] == 200 and row[2] > args.slow]
    total = sum(row[2] for row in run.rows)
    print(
        f"\n{len(run.rows)} calls in {total:.0f} s: {len(failed)} failed, {len(slow)} slow"
    )
    return 1 if args.check and (failed or slow) else 0


if __name__ == "__main__":
    sys.exit(main())
