"""Pitchlist contracts: data models and the data-layer interface.

FROZEN after task T2. Changes need all three humans to agree; then bump
CONTRACT_VERSION, note it in contracts/CHANGELOG.md and update CLAUDE.md §5
in the same commit.
"""

from typing import Literal, Protocol

from pydantic import BaseModel

CONTRACT_VERSION = "1.0.0"

SourceRank = Literal["PRIMARY", "FILING", "PRESS", "AGGREGATOR", "UNKNOWN"]


# --- 5.1 Models ---------------------------------------------------------------


class Source(BaseModel):
    name: str
    url: str | None = None
    date: str | None = None  # ISO date or partial ("2025-10")
    rank: SourceRank = "UNKNOWN"


class EntityRef(BaseModel):
    id: str  # Cala UUID
    name: str
    type: str  # Company | Organization | Person | FundingRound ...
    description: str | None = None


class Company(EntityRef):
    industries: list[str] = []
    stage: str | None = None
    country: str | None = None
    total_funding_text: str | None = None
    sources: list[Source] = []


class RoundInvestor(BaseModel):
    investor: EntityRef
    is_lead: bool | None = None  # None = unknown


class Round(BaseModel):
    id: str
    company_id: str
    label: str | None = None  # "Seed", "Series A" ...
    date: str | None = None
    amount_text: str | None = None
    amount_eur: float | None = None
    investors: list[RoundInvestor] = []
    sources: list[Source] = []


class PortfolioLink(BaseModel):
    investor_id: str
    company: EntityRef
    sources: list[Source] = []


class PersonLink(BaseModel):
    person: EntityRef
    company_id: str
    role: Literal["BOARD", "FOUNDER", "CEO", "EMPLOYEE"]
    sources: list[Source] = []


class Competitor(BaseModel):
    company: Company
    reason: str
    similarity: float | None = None


class Conflict(BaseModel):
    kind: Literal["PORTFOLIO", "BOARD"]
    competitor: EntityRef
    via_person: EntityRef | None = None
    sources: list[Source] = []


class Reason(BaseModel):
    text: str
    sources: list[Source] = []


class InvestorScore(BaseModel):
    investor: EntityRef
    score: float
    conflict: Conflict | None = None
    leads_in_space: int = 0
    rounds_in_space: int = 0
    last_lead_date: str | None = None
    warm_paths: list[Reason] = []
    reasons: list[Reason] = []


class FounderReport(BaseModel):
    company: Company
    competitors: list[Competitor]
    pitch: list[InvestorScore]
    skip: list[InvestorScore]


class InvestorCheck(BaseModel):
    investor: EntityRef
    company: Company
    conflicts: list[Conflict]
    competitors: list[Competitor]
    rounds: list[Round]


class Brief(BaseModel):
    investor_id: str
    company_id: str
    markdown: str
    citations: list[Source]


class AgentEvent(BaseModel):  # streamed by /api/jobs/{id}/stream and /api/chat
    type: Literal["step", "brief", "error", "done"]
    message: str | None = None
    brief: Brief | None = None


# --- 5.2 Data layer interface — A implements, B consumes ----------------------
# B only ever calls `data.get_store()`: FakeDataStore when USE_FAKE_STORE=true,
# else the real store.


class DataStore(Protocol):
    async def resolve(self, name: str, kind: Literal["company", "investor"]) -> list[EntityRef]: ...
    async def company(self, id: str) -> Company: ...
    async def rounds(self, company_id: str) -> list[Round]: ...
    async def investor_rounds(self, investor_id: str) -> list[Round]: ...
    async def portfolio(self, investor_id: str) -> list[PortfolioLink]: ...
    async def people(self, company_id: str) -> list[PersonLink]: ...
    async def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]: ...
    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]: ...
    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]: ...  # knowledge_search
