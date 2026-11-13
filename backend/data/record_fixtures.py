"""Record raw Cala responses for the demo cases (task A1).

Run from anywhere with the venv active:

    python -m data.record_fixtures            # record what is missing (safe to rerun)
    python -m data.record_fixtures --force    # re-record everything
    python -m data.record_fixtures --dry-run  # show what is already recorded

Every response is saved unedited under contracts/fixtures/raw/<kind>/<key>.json as
{"request": ..., "recorded_at": ..., "response": <Cala's JSON>}. A file that already exists is
not fetched again, so a run that stops (rate limit, network) continues where it left off.
raw/manifest.json lists which Cala ID belongs to which demo case.

Cala allows about 10 calls a minute on our key, so a full run takes 15-20 minutes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from data.config import RAW_DIR, env, load_env
from data.mappers import slug

# --- The demo cases (contracts/fixtures/README.md), pinned to Cala IDs -------------------------
# `alt` = other Cala entries for the same firm (Cala often has a Company and an Organization).

COMPANIES = {
    "kelluu": {
        "name": "Kelluu",
        "id": "78d7490a-dd04-5119-a7f1-e940b861219b",
        "alt": ["e4e92460-263b-4470-af82-a91cf153e453"],
    },
    "sensofusion": {
        "name": "Sensofusion",
        "id": "202e9283-6455-486f-8868-03c7e0d0cf29",
        "alt": ["5c699806-0fea-4e62-a594-717d4d85516c"],
    },
    "stendr": {"name": "Stendr", "id": "3afdc63c-b992-4b25-b69d-807ab346352d", "alt": []},
    "nestai": {"name": "NestAI", "id": "14359613-a45f-4804-892d-3b9dd9e927a9", "alt": []},
    # Nordic Air Defence has no company entity in Cala (13 Nov): only knowledge answers.
    "nordic-air-defence": {"name": "Nordic Air Defence", "id": None, "alt": []},
}

INVESTORS = {
    "tesi": {"name": "Tesi", "id": "df5be140-d50e-4e21-bb4f-d8f1e4ad3959", "alt": []},
    "maki-vc": {
        "name": "Maki.vc",
        "id": "415bc278-6ed1-4973-a684-07a8b8c5d855",
        "alt": ["8f0ff46d-d609-4ce0-b719-85f739b92ca3"],
    },
    "nato-innovation-fund": {
        "name": "NATO Innovation Fund",
        "id": "2ca07622-990d-40bf-a4fe-36434d43d6db",
        "alt": [],
    },
    "keen-venture-partners": {
        "name": "Keen Venture Partners",
        "id": "26cc4923-734a-4185-9ad2-4bdaa0efa20b",
        "alt": [],
    },
    "gungnir-capital": {
        "name": "Gungnir Capital",
        "id": "72d0da73-e0a2-4915-842e-0302e2cc0535",
        "alt": [],
    },
    "inventure": {"name": "Inventure", "id": "fd3ba350-0e55-40b5-96e3-013994777fdc", "alt": []},
    "sno-ventures": {
        "name": "SNÖ Ventures",
        "id": "4db7ebf9-b42b-42f9-a487-f63b1dcb9ce9",
        "alt": [],
    },
}

# Competitor candidates: one simple query per country (a single combined query is "too complex").
_CANDIDATE_QUERY = (
    "companies.industry=AEROSPACE_AND_DEFENSE.country={country}"
    ".funding_stage=Pre-Seed OR Seed OR Series A"
    ".return(name, description, funding_stage, total_funding).limit=15"
)
QUERIES = {
    "candidates-finland": _CANDIDATE_QUERY.format(country="Finland"),
    "candidates-sweden": _CANDIDATE_QUERY.format(country="Sweden"),
    "candidates-norway": _CANDIDATE_QUERY.format(country="Norway"),
    "candidates-counter-drone": (
        "Counter-drone and drone defence startups in the Nordic and Baltic countries: "
        "name, description, country, funding stage, total funding, investors"
    ),
}

# Sourced answers (knowledge_search): who invested and who led, per company and per investor.
QUESTIONS = {
    "rounds-kelluu": "Who invested in Kelluu and who led each of its funding rounds?",
    "rounds-sensofusion": "Who invested in Sensofusion and who led each of its funding rounds?",
    "rounds-stendr": "Who invested in Stendr and who led each of its funding rounds?",
    "rounds-nestai": "Who invested in NestAI and who led each of its funding rounds?",
    "rounds-nordic-air-defence": (
        "Who invested in Nordic Air Defence (NAD) and who led each of its funding rounds?"
    ),
    "investor-tesi-defence": (
        "Which defence technology companies has Tesi invested in, and which rounds did it lead?"
    ),
    "investor-maki-vc-defence": (
        "Which defence technology companies has Maki.vc invested in, and which rounds did it lead?"
    ),
}

MAX_CANDIDATES = 20  # candidate companies retrieved in full
MAX_ROUNDS_PER_INVESTOR = 15  # funding rounds retrieved per named investor
REL_LIMIT = 100  # edges per relationship in one retrieval

# Unknown names are ignored by Cala, so one list serves companies, investors and rounds.
PROPERTIES = [
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
    "total_funding_excluding_debt",
    "total_funding_excluding_debt_units",
    "employee_count",
    # FundingRound
    "round_label",
    "announcement_date",
    "transaction_value",
    "transaction_value_units",
    "instrument",
    "annotations",
]
REL_OUT = ["PARTICIPATES_IN_FUNDING_ROUND", "INVESTED_IN", "OPERATES_IN_INDUSTRY"]
REL_IN = [
    "PARTICIPATES_IN_FUNDING_ROUND",
    "INVESTED_IN",
    "IS_BOARD_MEMBER_OF",
    "FOUNDED",
    "IS_CEO_OF",
    "WORKS_AT",
]
ORG_TYPES = {"Company", "Organization"}


class BudgetExceeded(RuntimeError):
    pass


class Recorder:
    """Fetches from Cala once per (kind, key) and keeps the raw response on disk."""

    def __init__(
        self,
        client: httpx.Client,
        raw_dir: Path,
        *,
        min_interval: float = 6.5,
        force: bool = False,
        dry_run: bool = False,
        max_calls: int = 400,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
    ) -> None:
        self.client = client
        self.raw_dir = raw_dir
        self.min_interval = min_interval
        self.force = force
        self.dry_run = dry_run
        self.max_calls = max_calls
        self.sleep = sleep
        self.log = log
        self.calls = 0
        self.cached = 0
        self.failed: list[str] = []
        self._last_call = 0.0

    def path(self, kind: str, key: str) -> Path:
        return self.raw_dir / kind / f"{key}.json"

    def fetch(
        self,
        kind: str,
        key: str,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict | None:
        """Return Cala's JSON for this request, from disk if recorded, else from the API."""
        file = self.path(kind, key)
        if file.exists() and not self.force:
            self.cached += 1
            return json.loads(file.read_text())["response"]
        if self.dry_run:
            self.log(f"  missing  {kind}/{key}")
            return None
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"stopped after {self.calls} calls (--max-calls)")
        response = self._request(method, url, params=params, body=body)
        if response is None:
            self.failed.append(f"{kind}/{key}")
            return None
        envelope = {
            "request": {"method": method, "path": url, "params": params, "json": body},
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "response": response,
        }
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(envelope, indent=1, ensure_ascii=False) + "\n")
        return response

    def _request(
        self, method: str, url: str, *, params: dict | None, body: dict | None
    ) -> dict | None:
        backoff = [20.0, 30.0, 60.0, 60.0, 60.0]
        for attempt in range(len(backoff) + 1):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                self.sleep(wait)
            started = time.monotonic()
            self._last_call = started
            self.calls += 1
            try:
                reply = self.client.request(method, url, params=params, json=body)
                status = reply.status_code
            except httpx.HTTPError as exc:
                status, reply = 0, None
                self.log(f"  network error on {method} {url}: {exc!r}")
            ms = int((time.monotonic() - started) * 1000)
            if status == 200:
                self.log(f"  {method} {url} -> 200 in {ms} ms (call {self.calls})")
                return reply.json()
            if status in (0, 429) or status >= 500:
                if attempt < len(backoff):
                    self.log(f"  {method} {url} -> {status}; retrying in {backoff[attempt]:.0f} s")
                    self.sleep(backoff[attempt])
                    continue
            detail = reply.text[:200] if reply is not None else "no response"
            self.log(f"  {method} {url} -> {status}; giving up: {detail}")
            return None
        return None

    # --- Cala endpoints ---------------------------------------------------------------------

    def search(self, name: str) -> dict | None:
        return self.fetch(
            "entity_search", slug(name), "GET", "/entities", params={"name": name, "limit": 10}
        )

    def introspection(self, entity_type: str, entity_id: str) -> dict | None:
        return self.fetch(
            "introspection", entity_type, "GET", f"/entities/{entity_id}/introspection"
        )

    def entity(self, entity_id: str) -> dict | None:
        body = {
            "properties": PROPERTIES,
            "relationships": {
                "outgoing": {rel: {"limit": REL_LIMIT} for rel in REL_OUT},
                "incoming": {rel: {"limit": REL_LIMIT} for rel in REL_IN},
            },
        }
        response = self.fetch("entity", entity_id, "POST", f"/entities/{entity_id}", body=body)
        for direction, rels in ((response or {}).get("relationships") or {}).items():
            for rel, items in rels.items():
                if len(items) >= REL_LIMIT:
                    self.log(f"  note: {entity_id} {direction} {rel} hit the limit of {REL_LIMIT}")
        return response

    def query(self, key: str, text: str) -> dict | None:
        return self.fetch("knowledge_query", key, "POST", "/knowledge/query", body={"input": text})

    def answer(self, key: str, text: str) -> dict | None:
        return self.fetch(
            "knowledge_search", key, "POST", "/knowledge/search", body={"input": text}
        )


def related(entity: dict | None, direction: str, rel: str) -> list[dict]:
    if not entity:
        return []
    return ((entity.get("relationships") or {}).get(direction) or {}).get(rel) or []


def round_ids(entity: dict | None) -> list[str]:
    return [
        item["id"]
        for item in related(entity, "outgoing", "PARTICIPATES_IN_FUNDING_ROUND")
        if item.get("entity_type") == "FundingRound"
    ]


def candidate_ids(query_response: dict | None) -> list[str]:
    """Company/Organization entities that a candidate query mentions by a row's name."""
    if not query_response:
        return []
    names = {
        slug(str(row.get("name", "")))
        for row in query_response.get("results") or []
        if isinstance(row, dict) and row.get("name")
    }
    ids = []
    for entity in query_response.get("entities") or []:
        if entity.get("entity_type") not in ORG_TYPES:
            continue
        labels = {slug(entity.get("name", ""))} | {slug(m) for m in entity.get("mentions") or []}
        if labels & names:
            ids.append(entity["id"])
    return ids


def record_all(rec: Recorder) -> dict:
    """Record everything, most important first. Returns the manifest."""
    manifest: dict = {
        "companies": {},
        "investors": {},
        "candidate_company_ids": [],
        "extra_investor_ids": [],
        "round_ids": [],
        "queries": QUERIES,
        "questions": QUESTIONS,
    }
    rounds: list[str] = []

    def add_rounds(ids: list[str]) -> None:
        for rid in ids:
            if rid not in rounds:
                rounds.append(rid)

    rec.log("1/8 demo companies")
    extra_investors: list[str] = []
    for key, case in COMPANIES.items():
        manifest["companies"][key] = case
        for entity_id in [case["id"], *case["alt"]]:
            if not entity_id:
                continue
            entity = rec.entity(entity_id)
            add_rounds(round_ids(entity))
            for investor in related(entity, "incoming", "INVESTED_IN"):
                if investor["id"] not in extra_investors:
                    extra_investors.append(investor["id"])

    rec.log("2/8 named investors")
    investor_rounds: list[str] = []
    for key, case in INVESTORS.items():
        manifest["investors"][key] = case
        for entity_id in [case["id"], *case["alt"]]:
            entity = rec.entity(entity_id)
            for rid in round_ids(entity)[:MAX_ROUNDS_PER_INVESTOR]:
                if rid not in investor_rounds:
                    investor_rounds.append(rid)

    rec.log("3/8 funding rounds of the demo companies")
    for rid in list(rounds):
        rec.entity(rid)

    rec.log("4/8 other investors behind the demo companies")
    named = {i for case in INVESTORS.values() for i in [case["id"], *case["alt"]]}
    extra_investors = [i for i in extra_investors if i not in named]
    manifest["extra_investor_ids"] = extra_investors
    for entity_id in extra_investors:
        rec.entity(entity_id)

    rec.log("5/8 name searches and field maps")
    for case in [*COMPANIES.values(), *INVESTORS.values()]:
        rec.search(case["name"])
    rec.introspection("Company", COMPANIES["kelluu"]["id"])
    rec.introspection("Organization", INVESTORS["tesi"]["id"])
    if rounds:
        rec.introspection("FundingRound", rounds[0])
    people = related(rec.entity(COMPANIES["kelluu"]["id"]), "incoming", "IS_BOARD_MEMBER_OF")
    if people:
        rec.introspection("Person", people[0]["id"])

    rec.log("6/8 sourced answers")
    for key, text in QUESTIONS.items():
        rec.answer(key, text)

    rec.log("7/8 competitor candidates")
    demo = {i for case in COMPANIES.values() for i in [case["id"], *case["alt"]] if i}
    candidates: list[str] = []
    for key, text in QUERIES.items():
        for entity_id in candidate_ids(rec.query(key, text)):
            if entity_id not in candidates and entity_id not in demo:
                candidates.append(entity_id)
    candidates = candidates[:MAX_CANDIDATES]
    manifest["candidate_company_ids"] = candidates
    for entity_id in candidates:
        entity = rec.entity(entity_id)
        for rid in round_ids(entity):
            if rid not in rounds:
                rounds.append(rid)
                rec.entity(rid)

    rec.log("8/8 funding rounds of the named investors")
    for rid in investor_rounds:
        if rid not in rounds:
            rounds.append(rid)
        rec.entity(rid)

    manifest["round_ids"] = rounds
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true", help="re-record files that exist")
    parser.add_argument("--dry-run", action="store_true", help="list what is missing, call nothing")
    parser.add_argument("--max-calls", type=int, default=400)
    parser.add_argument("--min-interval", type=float, default=6.5, help="seconds between calls")
    args = parser.parse_args(argv)

    load_env()
    key = env("CALA_API_KEY")
    if not key and not args.dry_run:
        print("CALA_API_KEY is empty: put it in .env (see .env.example).", file=sys.stderr)
        return 2
    base = env("CALA_BASE_URL", "https://api.cala.ai/v1").rstrip("/")
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    with httpx.Client(base_url=base, headers=headers, timeout=180) as client:
        rec = Recorder(
            client,
            RAW_DIR,
            min_interval=args.min_interval,
            force=args.force,
            dry_run=args.dry_run,
            max_calls=args.max_calls,
        )
        try:
            manifest = record_all(rec)
        except BudgetExceeded as exc:
            print(f"{exc}. Run again to continue.", file=sys.stderr)
            return 1
        if not args.dry_run:
            file = RAW_DIR / "manifest.json"
            file.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
        print(f"done: {rec.calls} calls, {rec.cached} from disk, {len(rec.failed)} failed")
        for name in rec.failed:
            print(f"  failed: {name}")
    return 1 if rec.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
