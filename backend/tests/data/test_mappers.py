"""Cala JSON -> contract models, on small inputs shaped like real Cala responses."""

from contracts.schemas import EntityRef
from data.mappers import (
    country_of,
    label,
    map_backers,
    map_candidate_rows,
    map_company,
    map_people,
    map_portfolio,
    map_resolve,
    map_round,
    map_source,
    map_sourced_answer,
    map_sources,
    money_text,
    slug,
    to_eur,
)

PRESS = {
    "name": "tech.eu",
    "document": "https://tech.eu/kelluu",
    "date": "2026-04-14",
    "date_precision": "day",
    "source_rank": "PRESS",
}
PRIMARY = {"name": "nif.fund", "document": "https://nif.fund/kelluu", "source_rank": "PRIMARY"}


def edge(id, name, entity_type="Organization", **properties):
    return {"id": id, "name": name, "entity_type": entity_type, "properties": properties}


COMPANY = {
    "id": "c1",
    "name": "Kelluu Oy",
    "entity_type": "Company",
    "description": "Builds hydrogen airships.",
    "properties": {
        "description": {"value": "Builds hydrogen airships.", "sources": [PRIMARY]},
        "funding_stage": {"value": "SERIES_A", "sources": [PRIMARY, PRESS]},
        "total_funding": {"value": 15301500.0, "sources": [PRESS]},
        "total_funding_units": {"value": "EUR", "sources": []},
        "headquarters_address": {"value": "Joensuu, Finland", "sources": []},
    },
    "relationships": {
        "outgoing": {
            "OPERATES_IN_INDUSTRY": [edge("i1", "AEROSPACE_AND_DEFENSE", "Industry")],
            "PARTICIPATES_IN_FUNDING_ROUND": [
                edge("r1", "Series A", "FundingRound", role="ISSUER")
            ],
        },
        "incoming": {
            "INVESTED_IN": [edge("inv1", "Tesi", sources=[PRESS])],
            "IS_BOARD_MEMBER_OF": [edge("p1", "Jouni Lintu", "Person", sources=[PRIMARY])],
            "IS_CEO_OF": [edge("p2", "Janne Hietala", "Person")],
            "FOUNDED": [edge("p2", "Janne Hietala", "Person")],
            "WORKS_AT": [edge("p3", "Iida Mustonen", "Person", role="Head of People")],
        },
    },
}

ROUND = {
    "id": "r1",
    "name": "Series A",
    "entity_type": "FundingRound",
    "properties": {
        "round_label": {"value": "SERIES_A", "sources": [PRIMARY]},
        "announcement_date": {"value": "2026-04-14", "sources": [PRIMARY]},
        "transaction_value": {"value": 15000000.0, "sources": [PRESS]},
        "transaction_value_units": {"value": "EUR", "sources": []},
    },
    "relationships": {
        "outgoing": {},
        "incoming": {
            "PARTICIPATES_IN_FUNDING_ROUND": [
                edge("inv2", "NATO Innovation Fund", role="INVESTOR", is_lead=True),
                edge("inv1", "Tesi", role="INVESTOR", sources=[PRESS]),
                edge("c1", "Kelluu Oy", "Company", role="ISSUER"),
            ]
        },
    },
}


def test_helpers():
    assert slug("Maki.vc") == "maki-vc"
    assert label("SERIES_A") == "Series A"
    assert label("PRE_SEED") == "Pre-Seed"
    assert label("Series B") == "Series B"
    assert label(None) is None
    assert money_text(15301500.0, "EUR") == "€15.3M"
    assert money_text(15000000, "USD") == "$15M"
    assert money_text(2_400_000_000, "SEK") == "2.4B SEK"
    assert money_text(None, "EUR") is None
    assert to_eur(100.0, "EUR") == 100.0
    assert to_eur(100.0, "USD") == 92.0
    assert to_eur(100.0, "XXX") is None and to_eur("1", "EUR") is None
    assert country_of("Joensuu, Finland") == "Finland"
    assert country_of("Hakamäenkuja 1, 01510 VANTAA, FI-01510, FI") == "Finland"
    assert country_of(None, "Norwegian defence technology company") == "Norway"
    assert country_of(None, None) is None


def test_sources():
    source = map_source(PRESS)
    assert (source.name, source.url, source.date, source.rank) == (
        "tech.eu",
        "https://tech.eu/kelluu",
        "2026-04-14",
        "PRESS",
    )
    registry = map_source({"name": "SEC", "document": {"endpoint": "https://sec.gov/x"}})
    assert registry.url == "https://sec.gov/x" and registry.rank == "UNKNOWN"
    assert map_source({"name": "x", "source_rank": "BLOG"}).rank == "UNKNOWN"
    assert map_source("nonsense") is None
    assert len(map_sources([PRESS, PRESS, PRIMARY, None])) == 2


def test_company():
    company = map_company(COMPANY)
    assert company.id == "c1" and company.name == "Kelluu Oy" and company.type == "Company"
    assert company.industries == ["AEROSPACE_AND_DEFENSE"]
    assert company.stage == "Series A" and company.country == "Finland"
    assert company.total_funding_text == "€15.3M"
    assert {s.name for s in company.sources} == {"nif.fund", "tech.eu"}


def test_company_with_almost_nothing():
    company = map_company({"id": "x", "name": "Bare", "entity_type": "Organization"})
    assert company.stage is None and company.industries == [] and company.sources == []


def test_round_marks_the_lead_and_the_rest_as_not_lead():
    mapped = map_round(ROUND)
    assert mapped.company_id == "c1" and mapped.label == "Series A"
    assert mapped.date == "2026-04-14"
    assert mapped.amount_text == "€15M" and mapped.amount_eur == 15000000.0
    assert [(i.investor.name, i.is_lead) for i in mapped.investors] == [
        ("NATO Innovation Fund", True),
        ("Tesi", False),
    ]
    assert {s.name for s in mapped.sources} == {"nif.fund", "tech.eu"}


def test_round_without_a_marked_lead_leaves_it_unknown():
    edges = [
        edge("inv1", "Tesi", role="INVESTOR"),
        edge("c1", "Kelluu Oy", "Company", role="ISSUER"),
    ]
    raw = {**ROUND, "relationships": {"incoming": {"PARTICIPATES_IN_FUNDING_ROUND": edges}}}
    assert [i.is_lead for i in map_round(raw).investors] == [None]


def test_round_without_an_issuer_is_dropped():
    raw = {**ROUND, "relationships": {"incoming": {"PARTICIPATES_IN_FUNDING_ROUND": []}}}
    assert map_round(raw) is None


def test_portfolio_backers_and_people():
    investor = {
        "id": "inv1",
        "name": "Tesi",
        "entity_type": "Organization",
        "relationships": {
            "outgoing": {"INVESTED_IN": [edge("c1", "Kelluu Oy", "Company", sources=[PRESS])]}
        },
    }
    (link,) = map_portfolio(investor)
    assert (
        link.investor_id == "inv1" and link.company.id == "c1" and link.sources[0].rank == "PRESS"
    )

    (backer,) = map_backers(COMPANY)
    assert backer.investor_id == "inv1" and backer.company.name == "Kelluu Oy"

    people = map_people(COMPANY)
    assert [(p.person.name, p.role) for p in people] == [
        ("Jouni Lintu", "BOARD"),
        ("Janne Hietala", "FOUNDER"),
        ("Janne Hietala", "CEO"),
        ("Iida Mustonen", "EMPLOYEE"),
    ]
    assert all(p.company_id == "c1" for p in people)
    assert people[0].sources[0].rank == "PRIMARY"


def test_resolve_keeps_organisations_and_puts_funds_first():
    search = {
        "entities": [
            {
                "id": "1",
                "name": "Inflection AI",
                "entity_type": "Company",
                "description": "An AI lab",
            },
            {"id": "2", "name": "Pascal Inflection", "entity_type": "Person", "description": None},
            {
                "id": "3",
                "name": "Inflection",
                "entity_type": "Organization",
                "description": "A venture capital firm",
            },
        ]
    }
    assert [r.id for r in map_resolve(search, "investor")] == ["3", "1"]
    assert [r.id for r in map_resolve(search, "company")] == ["1", "3"]
    assert map_resolve(None, "company") == []
    assert isinstance(map_resolve(search, "company")[0], EntityRef)


def test_sourced_answer_ties_each_claim_to_its_sources():
    answer = {
        "content": "## Kelluu\nNATO Innovation Fund led the Series A.",
        "explainability": [
            {"content": "NATO Innovation Fund led the Series A.", "references": ["k1", "k2"]},
            {"content": "  ", "references": []},
            {"content": "Tesi also invested.", "references": ["missing"]},
        ],
        "context": [
            {
                "id": "k1",
                "content": "…",
                "origins": [
                    {
                        "source": {"name": "NIF", "url": "https://nif.fund"},
                        "document": {"name": "NIF leads €15M", "url": "https://nif.fund/kelluu"},
                    }
                ],
            },
            {"id": "k2", "content": "…", "origins": [{"source": {"name": "tech.eu", "url": "u"}}]},
        ],
    }
    markdown, reasons = map_sourced_answer(answer)
    assert markdown.startswith("## Kelluu")
    assert [r.text for r in reasons] == [
        "NATO Innovation Fund led the Series A.",
        "Tesi also invested.",
    ]
    assert [(s.name, s.url) for s in reasons[0].sources] == [
        ("NIF leads €15M", "https://nif.fund/kelluu"),
        ("tech.eu", "u"),
    ]
    assert reasons[1].sources == []
    assert map_sourced_answer(None) == ("", [])


def test_candidate_rows_need_an_entity():
    query = {
        "results": [
            {
                "name": "Acme Defence",
                "description": "Finnish maker of counter-drone radars",
                "funding_stage": "Seed",
                "total_funding": "~€4M",
            },
            {"name": "No Entity Oy", "description": "x"},
            {"error": "too complex"},
        ],
        "entities": [
            {
                "id": "a1",
                "name": "ACME DEFENCE OY",
                "entity_type": "Company",
                "mentions": ["Acme Defence"],
            },
            {"id": "f1", "name": "Finland", "entity_type": "Country", "mentions": ["Finland"]},
        ],
    }
    (company,) = map_candidate_rows(query)
    assert company.id == "a1" and company.name == "ACME DEFENCE OY"
    assert company.stage == "Seed" and company.total_funding_text == "~€4M"
    assert company.country == "Finland"
    assert map_candidate_rows(None) == []


def test_stage_helpers():
    from data.mappers import clean_stage, stage_index

    assert [stage_index(s) for s in ("PRE_SEED", "Pre-Seed", "preseed round")] == [0, 0, 0]
    assert stage_index("Seed") == 1 and stage_index("SERIES_A") == 2
    assert stage_index("Series A (Oct 2025)") == 2 and stage_index("Series B") == 3
    assert stage_index("Grant") is None and stage_index(None) is None
    assert clean_stage("Series A+ (multiple rounds)") == "Series A"
    assert clean_stage("Growth equity") == "Growth equity"
    assert clean_stage(None) is None
