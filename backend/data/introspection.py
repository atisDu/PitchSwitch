"""Which properties and relationships Cala has per entity type (task A4).

Cala's introspection answers for one entity and only lists what that entity has filled in, so the
map is the union over a few well-covered sample entities per type, plus a baseline of fields we
know exist. It is fetched once and kept in backend/data/introspection.json:

    python -m data.introspection      # refresh the file from live Cala (about 10 calls)

`fields_for("Company")` is what the store uses to ask only for fields that exist.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("introspection.json")

# Well-covered entities to introspect, per type.
SAMPLES = {
    "Company": [
        "78d7490a-dd04-5119-a7f1-e940b861219b",  # Kelluu Oy
        "415bc278-6ed1-4973-a684-07a8b8c5d855",  # Maki.vc
        "26cc4923-734a-4185-9ad2-4bdaa0efa20b",  # Keen Venture Partners
    ],
    "Organization": [
        "df5be140-d50e-4e21-bb4f-d8f1e4ad3959",  # Tesi
        "2ca07622-990d-40bf-a4fe-36434d43d6db",  # NATO Innovation Fund
        "fd3ba350-0e55-40b5-96e3-013994777fdc",  # Inventure
    ],
    "FundingRound": [
        "97d82be9-51db-59e4-bb04-f69213aff7e9",  # Kelluu Series A
        "7cf7864b-8de0-5b39-99c3-3754e678454a",  # Kelluu grant
    ],
    "Person": [
        "7993278e-4575-5987-be2e-c269dd2b9e2a",  # Janne Hietala (CEO, founder)
        "014ab9e4-cec1-5704-9f27-0b60a9a20e1c",  # Jouni Lintu (board)
    ],
}

# Fields we rely on; always part of the answer, even if no sample happened to have them.
BASELINE = {
    "Company": {
        "properties": [
            "name",
            "description",
            "funding_stage",
            "total_funding",
            "total_funding_units",
            "headquarters_address",
            "registered_address",
            "founding_date",
        ],
        "outgoing": ["PARTICIPATES_IN_FUNDING_ROUND", "OPERATES_IN_INDUSTRY", "INVESTED_IN"],
        "incoming": ["INVESTED_IN", "IS_BOARD_MEMBER_OF", "FOUNDED", "IS_CEO_OF", "WORKS_AT"],
    },
    "Organization": {
        "properties": ["name", "description", "registered_address", "headquarters_address"],
        "outgoing": ["PARTICIPATES_IN_FUNDING_ROUND", "OPERATES_IN_INDUSTRY", "INVESTED_IN"],
        "incoming": ["INVESTED_IN", "IS_BOARD_MEMBER_OF", "FOUNDED", "IS_CEO_OF", "WORKS_AT"],
    },
    "FundingRound": {
        "properties": [
            "name",
            "round_label",
            "announcement_date",
            "transaction_value",
            "transaction_value_units",
            "instrument",
        ],
        "outgoing": [],
        "incoming": ["PARTICIPATES_IN_FUNDING_ROUND"],
    },
    "Person": {
        "properties": ["name", "description"],
        "outgoing": ["IS_BOARD_MEMBER_OF", "FOUNDED", "IS_CEO_OF", "WORKS_AT"],
        "incoming": [],
    },
}


@dataclass(frozen=True)
class Fields:
    properties: tuple[str, ...]
    outgoing: tuple[str, ...]
    incoming: tuple[str, ...]

    def only(
        self,
        properties: list[str] | None = None,
        outgoing: list[str] | None = None,
        incoming: list[str] | None = None,
    ) -> Fields:
        """These fields, cut down to the wanted names that exist (order of `wanted` kept)."""

        def pick(wanted: list[str] | None, existing: tuple[str, ...]) -> tuple[str, ...]:
            return tuple(name for name in wanted or [] if name in existing)

        return Fields(
            pick(properties, self.properties),
            pick(outgoing, self.outgoing),
            pick(incoming, self.incoming),
        )


def _merge(*groups: dict) -> dict:
    merged: dict[str, list[str]] = {"properties": [], "outgoing": [], "incoming": []}
    for group in groups:
        for key, names in merged.items():
            for name in group.get(key) or []:
                if name not in names and name != "id" and "__" not in name:
                    names.append(name)
    return merged


@lru_cache(maxsize=1)
def _recorded() -> dict:
    if not PATH.exists():
        return {}
    return json.loads(PATH.read_text()).get("types") or {}


def fields_for(*entity_types: str) -> Fields:
    """The fields of one type, or the union of several: `fields_for("Company", "Organization")`
    is what to ask for when an ID may be either. Unknown types give empty fields."""
    recorded = _recorded()
    merged = _merge(
        *[BASELINE.get(entity_type, {}) for entity_type in entity_types],
        *[recorded.get(entity_type, {}) for entity_type in entity_types],
    )
    return Fields(tuple(merged["properties"]), tuple(merged["outgoing"]), tuple(merged["incoming"]))


def summarise(responses: list[dict]) -> dict:
    """The union of several introspection responses for one type."""
    return _merge(
        *[
            {
                "properties": response.get("properties") or [],
                "outgoing": (response.get("relationships") or {}).get("outgoing") or [],
                "incoming": (response.get("relationships") or {}).get("incoming") or [],
            }
            for response in responses
        ]
    )


async def refresh(client, path: Path = PATH, samples: dict[str, list[str]] = SAMPLES) -> dict:
    """Introspect the samples through `client` (a CalaClient) and rewrite the JSON file."""
    types = {}
    for entity_type, ids in samples.items():
        responses = await asyncio.gather(*[client.introspect(entity_id) for entity_id in ids])
        summary = summarise(list(responses))
        types[entity_type] = {
            **{key: sorted(names) for key, names in summary.items()},
            "samples": ids,
        }
    document = {
        "note": "Written by `python -m data.introspection`. Do not edit by hand.",
        "fetched_on": datetime.now(UTC).date().isoformat(),
        "types": types,
    }
    path.write_text(json.dumps(document, indent=1) + "\n")
    _recorded.cache_clear()
    return document


async def _main() -> None:
    from data.cala_client import CalaClient

    async with CalaClient.from_env() as cala:
        document = await refresh(cala)
        for entity_type, fields in document["types"].items():
            print(
                f"{entity_type}: {len(fields['properties'])} properties, "
                f"{len(fields['outgoing'])} outgoing, {len(fields['incoming'])} incoming"
            )
        print(cala.stats())


if __name__ == "__main__":
    asyncio.run(_main())
