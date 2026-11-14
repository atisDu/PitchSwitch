// Mirrors contracts/schemas.py (CONTRACT_VERSION 1.1.1) field for field.
// Do not change shapes here without a contract change (CLAUDE.md rule 4).
//
// Pydantic always serialises every field, so fields with defaults are present
// in the JSON: they are required here, and `X | None = None` becomes `X | null`.

export const CONTRACT_VERSION = "1.1.1";

export type SourceRank = "PRIMARY" | "FILING" | "PRESS" | "AGGREGATOR" | "UNKNOWN";

export interface Source {
  name: string;
  url: string | null;
  date: string | null; // ISO date or partial ("2025-10")
  rank: SourceRank;
}

export interface EntityRef {
  id: string; // Cala UUID
  name: string;
  type: string; // Company | Organization | Person | FundingRound ... (1.1.1: an investor can be a Person, an angel)
  description: string | null;
}

export interface Company extends EntityRef {
  industries: string[];
  stage: string | null;
  country: string | null;
  total_funding_text: string | null;
  sources: Source[];
}

export interface RoundInvestor {
  investor: EntityRef;
  is_lead: boolean | null; // null = unknown
}

export interface Round {
  id: string;
  company_id: string;
  label: string | null; // "Seed", "Series A" ...
  date: string | null;
  amount_text: string | null;
  amount_eur: number | null;
  investors: RoundInvestor[];
  sources: Source[];
}

export interface PortfolioLink {
  investor_id: string;
  company: EntityRef;
  sources: Source[];
}

export type PersonRole = "BOARD" | "FOUNDER" | "CEO" | "EMPLOYEE";

export interface PersonLink {
  person: EntityRef;
  company_id: string;
  role: PersonRole;
  sources: Source[];
}

export interface Competitor {
  company: Company;
  reason: string;
  similarity: number | null;
}

export type ConflictKind = "PORTFOLIO" | "BOARD";

export interface Conflict {
  kind: ConflictKind;
  competitor: EntityRef;
  via_person: EntityRef | null;
  sources: Source[];
}

export interface Reason {
  text: string;
  sources: Source[];
}

export type LeadData = "known" | "partial" | "unknown";

export interface InvestorScore {
  investor: EntityRef;
  score: number; // 0-100, higher = better fit
  conflicts: Conflict[]; // non-empty = this investor belongs in `skip`
  leads_in_space: number;
  rounds_in_space: number;
  // "known" = every round in space says who led, "partial" = some do,
  // "unknown" = none do (show rounds_in_space, say so).
  lead_data: LeadData;
  last_lead_date: string | null;
  deals_last_12m: number | null; // null = unknown
  warm_paths: Reason[];
  reasons: Reason[];
}

export interface FounderReport {
  company: Company;
  competitors: Competitor[];
  pitch: InvestorScore[]; // no conflicts; sorted by score, highest first
  skip: InvestorScore[]; // one or more conflicts; sorted by score, highest first
}

export interface InvestorCheck {
  investor: EntityRef;
  company: Company;
  conflicts: Conflict[];
  competitors: Competitor[];
  rounds: Round[]; // rounds of `company` AND of every competitor; group by Round.company_id
}

export interface Brief {
  investor_id: string;
  company_id: string;
  markdown: string; // cites with [n] markers: n is a 1-based index into `citations`
  citations: Source[];
}

export type AgentEventType = "step" | "text" | "brief" | "error" | "done";

export interface AgentEvent {
  // step = progress line, text = answer chunk (append to the previous ones),
  // brief = one finished brief, error = something failed, done = end of stream
  type: AgentEventType;
  message: string | null;
  brief: Brief | null;
  investor_name: string | null; // slush-prep: the pasted name this event belongs to
  investor: EntityRef | null; // slush-prep: the resolved investor, once known
  citations: Source[]; // chat: sent on `done`; [n] in the text is a 1-based index into it
}

// --- REST bodies and small responses (contracts/api.md) ----------------------

export type EntityKind = "company" | "investor";

export interface ResolveRequest {
  name: string;
  kind: EntityKind;
}

export interface FounderAnalyzeRequest {
  company_id: string;
  competitor_ids?: string[];
}

export interface InvestorCheckRequest {
  investor_id: string;
  company_id: string;
}

export interface BriefRequest {
  investor_id: string;
  company_id: string;
}

export interface SlushPrepRequest {
  company_id: string;
  investor_names: string[];
}

export interface SlushPrepResponse {
  job_id: string;
}

export interface ChatRequest {
  company_id?: string;
  investor_id?: string;
  message: string;
}

export interface HealthResponse {
  ok: true;
  contract_version: string;
}

export interface ApiErrorBody {
  error: string;
}
