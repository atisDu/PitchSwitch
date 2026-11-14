"""Pitchlist contracts: data models and the data-layer interface.

FROZEN after task T2. Changes need all three humans to agree; then bump
CONTRACT_VERSION, note it in contracts/CHANGELOG.md and update CLAUDE.md §5
in the same commit.
"""

from typing import Literal, Protocol

from pydantic import BaseModel

CONTRACT_VERSION = "1.1.1"

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
    score: float  # 0-100, higher = better fit
    conflicts: list[Conflict] = []  # non-empty = this investor belongs in `skip`
    leads_in_space: int = 0
    rounds_in_space: int = 0
    # How far leads_in_space rests on Cala's is_lead flag: "known" = every round in space
    # says who led, "partial" = some do, "unknown" = none do (show rounds_in_space, say so).
    lead_data: Literal["known", "partial", "unknown"] = "unknown"
    last_lead_date: str | None = None
    deals_last_12m: int | None = None  # None = unknown
    warm_paths: list[Reason] = []
    reasons: list[Reason] = []


class FounderReport(BaseModel):
    company: Company
    competitors: list[Competitor]
    pitch: list[InvestorScore]  # no conflicts; sorted by score, highest first
    skip: list[InvestorScore]  # one or more conflicts; sorted by score, highest first


class InvestorCheck(BaseModel):
    investor: EntityRef
    company: Company
    conflicts: list[Conflict]
    competitors: list[Competitor]
    rounds: list[Round]  # rounds of `company` AND of every competitor; group by Round.company_id


class Brief(BaseModel):
    investor_id: str
    company_id: str
    markdown: str  # cites with [n] markers: n is a 1-based index into `citations`
    citations: list[Source]


class AgentEvent(BaseModel):  # streamed by /api/jobs/{id}/stream and /api/chat
    # step = progress line, text = answer chunk (append to the previous ones),
    # brief = one finished brief, error = something failed, done = end of stream
    type: Literal["step", "text", "brief", "error", "done"]
    message: str | None = None  # step: what is happening; text: the chunk; error: what failed
    brief: Brief | None = None
    investor_name: str | None = None  # slush-prep: the pasted name this event belongs to
    investor: EntityRef | None = None  # slush-prep: the resolved investor, once known
    # chat: sent on the `done` event; [n] in the streamed text is a 1-based index into it
    citations: list[Source] = []


# --- 5.2 Data layer interface — A implements, B consumes ----------------------
# B only ever calls `data.get_store()`: FakeDataStore when USE_FAKE_STORE=true,
# else the real store.


class DataStore(Protocol):
    async def resolve(self, name: str, kind: Literal["company", "investor"]) -> list[EntityRef]: ...
    # company(): `id` may be any organisation, including an investor, or a person who invests
    # (an angel; then Company.type is "Person"). investor_rounds(), portfolio() and people()
    # accept such a person's ID too and return [] when nothing is known; they never raise for it
    async def company(self, id: str) -> Company: ...
    async def rounds(self, company_id: str) -> list[Round]: ...
    async def investor_rounds(self, investor_id: str) -> list[Round]: ...
    async def portfolio(self, investor_id: str) -> list[PortfolioLink]: ...
    # people(): also accepts an investor ID and returns that investor's own people
    # (PersonLink.company_id is then the investor ID); needed for BOARD conflicts
    async def people(self, company_id: str) -> list[PersonLink]: ...
    async def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]: ...
    # co_investors(): [] when nothing is known yet (before the batch job); never raises for that
    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]: ...
    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]: ...  # knowledge_search
