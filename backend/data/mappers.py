"""Cala JSON -> contract models. One small pure function per model.

Used to build the fixtures (A2) and by the real store (A6-A9). Nothing here calls the network,
and nothing raises on missing or odd data: a field that can't be read becomes None or [].
"""

from __future__ import annotations

import re

from contracts.schemas import (
    Company,
    EntityRef,
    PersonLink,
    PortfolioLink,
    Reason,
    Round,
    RoundInvestor,
    Source,
)
from data.parsers import to_eur

RANKS = {"PRIMARY", "FILING", "PRESS", "AGGREGATOR"}
ORG_TYPES = {"Company", "Organization"}
INVESTOR_WORDS = ("venture", "capital", "fund", "invest", "equity", "angel", "accelerator")

CURRENCY_SIGNS = {"EUR": "€", "USD": "$", "GBP": "£"}

COUNTRY_CODES = {
    "FI": "Finland",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "IS": "Iceland",
    "EE": "Estonia",
    "LV": "Latvia",
    "LT": "Lithuania",
    "DE": "Germany",
    "FR": "France",
    "NL": "Netherlands",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "US": "United States",
    "LU": "Luxembourg",
    "CH": "Switzerland",
    "PL": "Poland",
}
COUNTRY_ADJECTIVES = {
    "finnish": "Finland",
    "swedish": "Sweden",
    "norwegian": "Norway",
    "danish": "Denmark",
    "icelandic": "Iceland",
    "estonian": "Estonia",
    "latvian": "Latvia",
    "lithuanian": "Lithuania",
    "german": "Germany",
    "french": "France",
    "dutch": "Netherlands",
    "british": "United Kingdom",
    "american": "United States",
    "luxembourg": "Luxembourg",
    "swiss": "Switzerland",
    "polish": "Poland",
    "italian": "Italy",
    "spanish": "Spain",
    "belgian": "Belgium",
    "austrian": "Austria",
    "irish": "Ireland",
    "czech": "Czechia",
    "portuguese": "Portugal",
    "canadian": "Canada",
    "israeli": "Israel",
    "ukrainian": "Ukraine",
}

PERSON_ROLES = {
    "IS_BOARD_MEMBER_OF": "BOARD",
    "FOUNDED": "FOUNDER",
    "IS_CEO_OF": "CEO",
    "WORKS_AT": "EMPLOYEE",
}


# --- Small helpers ---------------------------------------------------------------------------


def slug(text: str) -> str:
    """Lowercase, non-alphanumerics to '-': the `slug` used in fixture file names."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


LEGAL_SUFFIXES = {
    "oy", "oyj", "ab", "as", "asa", "aps", "ky", "ou", "ltd", "limited", "inc", "llc", "gmbh",
    "plc", "sa", "bv", "nv", "spa", "srl", "corp", "co", "ag", "se",
}  # fmt: skip


def name_key(name: str) -> str:
    """A name without its legal form, for spotting two entries of one firm:
    'Kelluu Oy' and 'Kelluu' -> 'kelluu'; 'MAKI.VC FUND I Ky' -> 'maki-vc-fund-i'."""
    words = slug(name.replace("ü", "u").replace("Ü", "U")).split("-")
    while len(words) > 1 and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return "-".join(words)


def prop(entity: dict | None, name: str):
    """A property's value from an entity retrieval, or None."""
    cell = ((entity or {}).get("properties") or {}).get(name)
    return cell.get("value") if isinstance(cell, dict) else cell


def prop_sources(entity: dict | None, *names: str) -> list[Source]:
    """The sources of the given properties, merged."""
    raw: list = []
    for name in names:
        cell = ((entity or {}).get("properties") or {}).get(name)
        if isinstance(cell, dict):
            raw.extend(cell.get("sources") or [])
    return map_sources(raw)


def related(entity: dict | None, direction: str, rel: str) -> list[dict]:
    """The edges of one relationship: each has id, name, entity_type and edge `properties`."""
    return (((entity or {}).get("relationships") or {}).get(direction) or {}).get(rel) or []


def edge_sources(edge: dict) -> list[Source]:
    return map_sources((edge.get("properties") or {}).get("sources") or [])


def merge_sources(*groups: list[Source]) -> list[Source]:
    """Join source lists, dropping repeats (same name and URL), keeping order."""
    seen: set[tuple[str, str | None]] = set()
    merged: list[Source] = []
    for group in groups:
        for source in group:
            key = (source.name, source.url)
            if key not in seen:
                seen.add(key)
                merged.append(source)
    return merged


def label(code: str | None) -> str | None:
    """'SERIES_A' -> 'Series A', 'PRE_SEED' -> 'Pre-Seed'. Already-readable text is kept."""
    if not code or not isinstance(code, str):
        return None
    if code != code.upper():
        return code
    text = code.replace("_", " ").title()
    return text.replace("Pre Seed", "Pre-Seed").replace("Ipo", "IPO")


def money_text(value, units: str | None) -> str | None:
    """15301500.0, 'EUR' -> '€15.3M'. None when there is no number."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    units = (units or "").upper()
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            number = f"{value / size:.1f}".removesuffix(".0") + suffix
            break
    else:
        number = f"{value:.0f}"
    sign = CURRENCY_SIGNS.get(units)
    if sign:
        return f"{sign}{number}"
    return f"{number} {units}".strip()


def country_of(address: str | None, description: str | None = None) -> str | None:
    """Country from an address ('Joensuu, Finland', '..., FI-01510, FI'), else the description."""
    if address:
        last = address.split(",")[-1].strip()
        if last.upper() in COUNTRY_CODES:
            return COUNTRY_CODES[last.upper()]
        if last and not any(ch.isdigit() for ch in last):
            return last
    for word in re.findall(r"[a-z]+", (description or "").lower()):
        if word in COUNTRY_ADJECTIVES:
            return COUNTRY_ADJECTIVES[word]
    return None


# --- Models ------------------------------------------------------------------------------------


def map_source(raw: dict) -> Source | None:
    """One Cala source: {name, document, date, source_rank}. `document` is a URL or an object."""
    if not isinstance(raw, dict):
        return None
    document = raw.get("document")
    if isinstance(document, dict):
        url = document.get("url") or document.get("endpoint")
    else:
        url = document
    name = raw.get("name") or (url or "")
    if not name:
        return None
    rank = raw.get("source_rank")
    return Source(
        name=str(name),
        url=url if isinstance(url, str) and url else None,
        date=raw.get("date") if isinstance(raw.get("date"), str) else None,
        rank=rank if rank in RANKS else "UNKNOWN",
    )


def map_sources(raw: list | None) -> list[Source]:
    return merge_sources([s for s in (map_source(item) for item in raw or []) if s])


def map_entity_ref(raw: dict) -> EntityRef:
    """Any Cala object with id, name and entity_type (search hit, edge, retrieval)."""
    return EntityRef(
        id=raw["id"],
        name=raw.get("name") or raw["id"],
        type=raw.get("entity_type") or "Entity",
        description=raw.get("description") or None,
    )


def map_company(entity: dict) -> Company:
    """An entity retrieval of a company or an investor -> Company."""
    description = prop(entity, "description") or entity.get("description")
    address = prop(entity, "headquarters_address") or prop(entity, "registered_address")
    funding = prop(entity, "total_funding")
    return Company(
        id=entity["id"],
        name=entity.get("name") or prop(entity, "name") or entity["id"],
        type=entity.get("entity_type") or "Company",
        description=description or None,
        industries=[
            edge["name"]
            for edge in related(entity, "outgoing", "OPERATES_IN_INDUSTRY")
            if edge.get("name")
        ],
        stage=label(prop(entity, "funding_stage")),
        country=country_of(address, description),
        total_funding_text=money_text(funding, prop(entity, "total_funding_units")),
        sources=prop_sources(
            entity, "description", "funding_stage", "total_funding", "headquarters_address", "name"
        ),
    )


def fill_gaps(main: Company, other: Company) -> Company:
    """`main`, with empty fields taken from `other` and the sources of both."""
    update = {
        field: getattr(other, field)
        for field in ("description", "stage", "country", "total_funding_text", "industries")
        if not getattr(main, field) and getattr(other, field)
    }
    update["sources"] = merge_sources(main.sources, other.sources)
    return main.model_copy(update=update)


def map_round(entity: dict) -> Round | None:
    """A FundingRound retrieval -> Round. None if the round has no issuing company."""
    edges = related(entity, "incoming", "PARTICIPATES_IN_FUNDING_ROUND")
    issuers = [e for e in edges if (e.get("properties") or {}).get("role") == "ISSUER"]
    if not issuers:
        return None
    backers = [e for e in edges if (e.get("properties") or {}).get("role") == "INVESTOR"]
    # Cala only marks the lead. If a lead is marked, the others are known not to lead.
    lead_known = any((e.get("properties") or {}).get("is_lead") is True for e in backers)
    investors = []
    for edge in backers:
        flag = (edge.get("properties") or {}).get("is_lead")
        is_lead = bool(flag) if lead_known or isinstance(flag, bool) else None
        investors.append(RoundInvestor(investor=map_entity_ref(edge), is_lead=is_lead))
    value = prop(entity, "transaction_value")
    units = prop(entity, "transaction_value_units")
    return Round(
        id=entity["id"],
        company_id=issuers[0]["id"],
        label=label(prop(entity, "round_label")) or entity.get("name") or None,
        date=prop(entity, "announcement_date"),
        amount_text=money_text(value, units),
        amount_eur=to_eur(value, units),
        investors=investors,
        sources=merge_sources(
            prop_sources(entity, "announcement_date", "transaction_value", "round_label"),
            *[edge_sources(edge) for edge in edges],
        ),
    )


def map_portfolio(entity: dict) -> list[PortfolioLink]:
    """An investor retrieval -> the companies it invested in (outgoing INVESTED_IN)."""
    return [
        PortfolioLink(
            investor_id=entity["id"], company=map_entity_ref(edge), sources=edge_sources(edge)
        )
        for edge in related(entity, "outgoing", "INVESTED_IN")
    ]


def map_backers(entity: dict) -> list[PortfolioLink]:
    """A company retrieval -> one link per investor behind it (incoming INVESTED_IN)."""
    company = map_entity_ref(entity)
    return [
        PortfolioLink(investor_id=edge["id"], company=company, sources=edge_sources(edge))
        for edge in related(entity, "incoming", "INVESTED_IN")
    ]


def map_people(entity: dict) -> list[PersonLink]:
    """A company or investor retrieval -> its board, founders, CEO and employees."""
    people = []
    for rel, role in PERSON_ROLES.items():
        for edge in related(entity, "incoming", rel):
            people.append(
                PersonLink(
                    person=map_entity_ref(edge),
                    company_id=entity["id"],
                    role=role,
                    sources=edge_sources(edge),
                )
            )
    return people


_INVESTOR_IN_TEXT = re.compile(r"\b(venture|capital|fund|invest|private equity|angel|accelerator)")
_INVESTOR_NAME_WORDS = {"ventures", "venture", "capital", "fund", "vc", "partners", "invest"}


def looks_like_investor(ref: EntityRef) -> bool:
    """Reads like an investor: by its description, or by a whole word of its name.
    ("Inventure Foods" does not count just because "venture" hides in the name.)"""
    if _INVESTOR_IN_TEXT.search((ref.description or "").lower()):
        return True
    return bool(set(slug(ref.name).split("-")) & _INVESTOR_NAME_WORDS)


def map_resolve(
    search_response: dict | None, kind: str, query: str | None = None
) -> list[EntityRef]:
    """A name search -> companies/organisations only, best match first.

    Guards against matches like "Inflection" (the VC) -> Inflection AI: people, products and
    places are dropped; for kind="investor" entries that read like an investor come first;
    then entries whose name is exactly the query (legal form aside) beat longer names.
    """
    refs = [
        map_entity_ref(hit)
        for hit in (search_response or {}).get("entities") or []
        if hit.get("entity_type") in ORG_TYPES and hit.get("id")
    ]
    wanted = name_key(query) if query else None

    def rank(ref: EntityRef) -> tuple:
        return (
            kind == "investor" and not looks_like_investor(ref),
            wanted is not None and name_key(ref.name) != wanted,
        )

    return sorted(refs, key=rank)


def map_sourced_answer(search_response: dict | None) -> tuple[str, list[Reason]]:
    """A knowledge_search answer -> (markdown, one Reason per claim with its sources)."""
    response = search_response or {}
    origins: dict[str, list[Source]] = {}
    for bit in response.get("context") or []:
        sources = []
        for origin in bit.get("origins") or []:
            document = origin.get("document") or {}
            site = origin.get("source") or {}
            url = document.get("url") or site.get("url")
            name = document.get("name") or site.get("name") or url
            if name:
                sources.append(Source(name=str(name), url=url or None))
        origins[bit.get("id")] = sources
    reasons = []
    for step in response.get("explainability") or []:
        text = (step.get("content") or "").strip()
        if not text:
            continue
        sources = merge_sources(*[origins.get(ref, []) for ref in step.get("references") or []])
        reasons.append(Reason(text=text, sources=sources))
    return response.get("content") or "", reasons


def map_candidate_rows(query_response: dict | None) -> list[Company]:
    """A knowledge_query for companies -> Company per row that Cala tied to an entity."""
    response = query_response or {}
    by_label: dict[str, dict] = {}
    for entity in response.get("entities") or []:
        if entity.get("entity_type") in ORG_TYPES:
            for text in [entity.get("name") or "", *(entity.get("mentions") or [])]:
                by_label.setdefault(slug(text), entity)
    companies = []
    for row in response.get("results") or []:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        entity = by_label.get(slug(str(row["name"])))
        if not entity:
            continue
        description = row.get("description")
        country = row.get("country")
        companies.append(
            Company(
                id=entity["id"],
                name=entity.get("name") or str(row["name"]),
                type=entity.get("entity_type") or "Company",
                description=str(description) if description else None,
                stage=label(str(row["funding_stage"])) if row.get("funding_stage") else None,
                country=str(country) if country else country_of(None, description),
                total_funding_text=str(row["total_funding"]) if row.get("total_funding") else None,
            )
        )
    return companies
