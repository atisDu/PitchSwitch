"""The contracts import cleanly and behave as CLAUDE.md §5 says."""

import inspect

from contracts import schemas
from contracts.schemas import (
    CONTRACT_VERSION,
    AgentEvent,
    Brief,
    Company,
    Conflict,
    DataStore,
    EntityRef,
    FounderReport,
    InvestorScore,
    PersonLink,
    Round,
    RoundInvestor,
    Source,
)

MODEL_NAMES = [
    "Source",
    "EntityRef",
    "Company",
    "RoundInvestor",
    "Round",
    "PortfolioLink",
    "PersonLink",
    "Competitor",
    "Conflict",
    "Reason",
    "InvestorScore",
    "FounderReport",
    "InvestorCheck",
    "Brief",
    "AgentEvent",
]

STORE_METHODS = [
    "resolve",
    "company",
    "rounds",
    "investor_rounds",
    "portfolio",
    "people",
    "candidate_competitors",
    "co_investors",
    "sourced_answer",
]


def test_version():
    assert CONTRACT_VERSION == "1.2.0"


def test_all_models_exist():
    for name in MODEL_NAMES:
        assert hasattr(schemas, name), name


def test_datastore_methods_are_async():
    for name in STORE_METHODS:
        assert inspect.iscoroutinefunction(getattr(DataStore, name)), name


def test_defaults():
    src = Source(name="Example")
    assert src.rank == "UNKNOWN" and src.url is None and src.date is None
    ref = EntityRef(id="1", name="Acme", type="Company")
    assert RoundInvestor(investor=ref).is_lead is None
    company = Company(id="1", name="Acme", type="Company")
    assert company.industries == [] and company.sources == []
    score = InvestorScore(investor=ref, score=1.0)
    assert score.conflicts == [] and score.leads_in_space == 0 and score.reasons == []
    assert score.lead_data == "unknown" and score.deals_last_12m is None
    event = AgentEvent(type="text", message="chunk")
    assert event.citations == [] and event.investor is None and event.investor_name is None


def test_mutable_defaults_are_not_shared():
    a = Round(id="r1", company_id="1")
    b = Round(id="r2", company_id="1")
    a.sources.append(Source(name="x"))
    assert b.sources == []


def test_literals_are_enforced():
    ref = EntityRef(id="1", name="Acme", type="Company")
    for bad in (
        lambda: Source(name="x", rank="BLOG"),
        lambda: PersonLink(person=ref, company_id="1", role="ADVISOR"),
        lambda: Conflict(kind="OTHER", competitor=ref),
        lambda: AgentEvent(type="progress"),
        lambda: InvestorScore(investor=ref, score=1.0, lead_data="guess"),
    ):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("invalid literal accepted")


def test_json_round_trip():
    ref = EntityRef(id="inv", name="Fund", type="Organization")
    rival = EntityRef(id="r", name="Rival", type="Company")
    company = Company(id="c", name="Acme", type="Company", sources=[Source(name="s", rank="PRESS")])
    report = FounderReport(
        company=company,
        competitors=[],
        pitch=[InvestorScore(investor=ref, score=2.5)],
        skip=[
            InvestorScore(
                investor=ref,
                score=0.0,
                conflicts=[Conflict(kind="PORTFOLIO", competitor=rival)],
                lead_data="partial",
                deals_last_12m=3,
            )
        ],
    )
    assert FounderReport.model_validate_json(report.model_dump_json()) == report
    brief = Brief(investor_id="inv", company_id="c", markdown="# x", citations=[])
    event = AgentEvent(type="brief", brief=brief, investor_name="Fund", investor=ref)
    assert AgentEvent.model_validate_json(event.model_dump_json()) == event
