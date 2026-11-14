// Mock of B's REST API (contracts/api.md), served from contracts/fixtures/models/.
// Pure request → response logic; mock/server.ts wraps it in an HTTP server.
// The founder/check/brief/event files are A's *samples* (real facts, placeholder
// ranking); B's API replaces them at CP3 (task C8).

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fitForCheck, fitForRaise } from "./funding.ts";
import type {
  AgentEvent,
  Brief,
  EntityKind,
  EntityRef,
  FounderReport,
  InvestorCheck,
  InvestorScore,
  Round,
} from "../lib/types.ts";

export interface IndexEntity extends EntityRef {
  kind: EntityKind;
}

export interface FixtureIndex {
  contract_version: string;
  aliases: Record<string, string>;
  entities: IndexEntity[];
  files: string[];
}

export type MockResult =
  | { kind: "json"; status: number; body: unknown }
  | { kind: "stream"; events: AgentEvent[] };

/** Same rule as backend/data/mappers.py `slug()`. */
export function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const json = (body: unknown, status = 200): MockResult => ({ kind: "json", status, body });
const error = (status: number, message: string): MockResult => json({ error: message }, status);

/** An optional positive amount: undefined when absent, null when present but invalid (422). */
function amount(v: unknown): number | undefined | null {
  if (v === undefined || v === null) return undefined;
  return typeof v === "number" && Number.isFinite(v) && v > 0 ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

export class MockApi {
  private dir: string;
  private index: FixtureIndex;
  private files: Set<string>;
  private jobs = new Map<string, AgentEvent[]>();
  private nextJob = 1;

  constructor(dir: string) {
    this.dir = dir;
    this.index = this.read<FixtureIndex>("index.json");
    this.files = new Set(this.index.files);
  }

  private read<T>(file: string): T {
    return JSON.parse(readFileSync(join(this.dir, file), "utf8")) as T;
  }

  private tryRead<T>(file: string): T | null {
    return this.files.has(file) ? this.read<T>(file) : null;
  }

  /** Cala has several IDs for one firm; fixtures are keyed by the canonical one. */
  private canonical(id: string): string {
    return this.index.aliases[id] ?? id;
  }

  handle(method: string, path: string, body: Record<string, unknown> = {}): MockResult {
    const route = `${method} ${path.replace(/\/+$/, "")}`;
    const job = /^GET \/api\/jobs\/([^/]+)\/stream$/.exec(route);
    if (job) return this.jobStream(decodeURIComponent(job[1]));

    switch (route) {
      case "GET /api/health":
        return json({ ok: true, contract_version: this.index.contract_version });
      case "POST /api/resolve":
        return this.resolve(body);
      case "POST /api/founder/analyze":
        return this.founder(body);
      case "POST /api/investor/check":
        return this.investorCheck(body);
      case "POST /api/brief":
        return this.brief(body);
      case "POST /api/slush-prep":
        return this.slushPrep(body);
      case "POST /api/chat":
        return str(body.message)
          ? { kind: "stream", events: this.read<AgentEvent[]>("agent_events_chat.json") }
          : error(422, "message is required");
      default:
        return error(404, `No route ${route}`);
    }
  }

  private resolve(body: Record<string, unknown>): MockResult {
    const name = str(body.name);
    const kind = body.kind;
    if (!name) return error(422, "name is required");
    if (kind !== "company" && kind !== "investor") {
      return error(422, 'kind must be "company" or "investor"');
    }
    const s = slug(name);
    const recorded = this.tryRead<EntityRef[]>(`resolve_${kind}_${s}.json`);
    if (recorded) return json(recorded);
    // Not a recorded search: fuzzy match on every entity the fixtures know.
    const hits = this.index.entities
      .filter((e) => e.kind === kind && s && slug(e.name).includes(s))
      .slice(0, 10)
      .map(({ id, name, type, description }) => ({ id, name, type, description }));
    return json(hits);
  }

  private founder(body: Record<string, unknown>): MockResult {
    const id = str(body.company_id);
    if (!id) return error(422, "company_id is required");
    const target = amount(body.target_amount_eur);
    if (target === null) return error(422, "target_amount_eur must be a positive number");
    const report = this.tryRead<FounderReport>(`founder_report_${this.canonical(id)}.json`);
    if (!report) return error(404, "The mock has no founder report for this company.");
    const ids = body.competitor_ids;
    const ranked = Array.isArray(ids) ? restrictToCompetitors(report, new Set(ids.map(String))) : report;
    // Until B21: funding_fit from the investor's recorded round sizes (mock/funding.ts).
    const withFit = (s: InvestorScore): InvestorScore => ({
      ...s,
      funding_fit:
        target === undefined
          ? null
          : fitForRaise(target, s.investor.name, this.tryRead<Round[]>(`investor_rounds_${s.investor.id}.json`) ?? []),
    });
    return json({ ...ranked, pitch: ranked.pitch.map(withFit), skip: ranked.skip.map(withFit) });
  }

  private investorCheck(body: Record<string, unknown>): MockResult {
    const inv = str(body.investor_id);
    const co = str(body.company_id);
    if (!inv || !co) return error(422, "investor_id and company_id are required");
    const maxCheck = amount(body.max_check_eur);
    if (maxCheck === null) return error(422, "max_check_eur must be a positive number");
    const check = this.tryRead<InvestorCheck>(
      `investor_check_${this.canonical(inv)}_${this.canonical(co)}.json`,
    );
    if (!check) return error(404, "The mock has no investor check for this pair.");
    const own = check.rounds.filter((r) => r.company_id === check.company.id);
    return json({
      ...check,
      funding_fit: maxCheck === undefined ? null : fitForCheck(maxCheck, check.company.name, own),
    });
  }

  private brief(body: Record<string, unknown>): MockResult {
    const inv = str(body.investor_id);
    const co = str(body.company_id);
    if (!inv || !co) return error(422, "investor_id and company_id are required");
    const brief = this.tryRead<Brief>(`brief_${this.canonical(inv)}_${this.canonical(co)}.json`);
    return brief ? json(brief) : error(404, "The mock has no brief for this pair.");
  }

  private slushPrep(body: Record<string, unknown>): MockResult {
    const names = body.investor_names ?? [];
    const allSlush = body.all_slush_investors === true; // B17: names optional then
    if (!str(body.company_id)) return error(422, "company_id is required");
    if (!Array.isArray(names) || (names.length === 0 && !allSlush)) {
      return error(422, "investor_names must be a non-empty list, or all_slush_investors true");
    }
    // The recorded stream is replayed whatever names were pasted.
    const id = `mock-job-${this.nextJob++}`;
    this.jobs.set(id, this.read<AgentEvent[]>("agent_events_slush_prep.json"));
    return json({ job_id: id });
  }

  private jobStream(id: string): MockResult {
    const events = this.jobs.get(id);
    return events ? { kind: "stream", events } : error(404, `No job ${id}`);
  }
}

/**
 * What B does with `competitor_ids`: rank against exactly those competitors.
 * The mock approximates it: drop the other competitors and the conflicts that
 * pointed at them; a Skip investor left with no conflict moves to Pitch.
 */
export function restrictToCompetitors(report: FounderReport, keep: Set<string>): FounderReport {
  const competitors = report.competitors.filter((c) => keep.has(c.company.id));
  const pitch: InvestorScore[] = [...report.pitch];
  const skip: InvestorScore[] = [];
  for (const s of report.skip) {
    const conflicts = s.conflicts.filter((c) => c.kind === "SANCTION" || keep.has(c.competitor.id)); // a sanction is no competitor
    (conflicts.length ? skip : pitch).push({ ...s, conflicts });
  }
  const byScore = (a: InvestorScore, b: InvestorScore) => b.score - a.score;
  return { ...report, competitors, pitch: pitch.sort(byScore), skip: skip.sort(byScore) };
}
