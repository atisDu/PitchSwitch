import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import type { AgentEvent, EntityRef, FounderReport, InvestorCheck } from "../lib/types.ts";
import { MockApi, restrictToCompetitors, slug, type FixtureIndex } from "./handlers.ts";

const DIR = join(dirname(fileURLToPath(import.meta.url)), "../../contracts/fixtures/models");
const index = JSON.parse(readFileSync(join(DIR, "index.json"), "utf8")) as FixtureIndex & {
  founder_mode: { company_id: string }[];
  investor_mode: { investor_id: string; company_id: string }[];
  briefs: { investor_id: string; company_id: string }[];
};
const api = new MockApi(DIR);

function ok<T>(method: string, path: string, body?: Record<string, unknown>): T {
  const r = api.handle(method, path, body);
  assert.equal(r.kind, "json");
  if (r.kind !== "json") throw new Error("unreachable");
  assert.equal(r.status, 200, JSON.stringify(r.body));
  return r.body as T;
}

function status(method: string, path: string, body?: Record<string, unknown>): number {
  const r = api.handle(method, path, body);
  return r.kind === "json" ? r.status : 200;
}

test("slug matches the backend rule", () => {
  assert.equal(slug("SNÖ Ventures"), "sn-ventures");
  assert.equal(slug("  Maki.vc "), "maki-vc");
  assert.equal(slug("Nordic Air Defence"), "nordic-air-defence");
});

test("health reports the contract version", () => {
  // Read from the fixtures, so a contract bump (A rebuilds index.json) doesn't break this test.
  assert.deepEqual(ok("GET", "/api/health"), { ok: true, contract_version: index.contract_version });
});

test("resolve: recorded searches, fuzzy fallback, validation", () => {
  const tesi = ok<EntityRef[]>("POST", "/api/resolve", { name: "Tesi", kind: "investor" });
  assert.equal(tesi[0].id, "df5be140-d50e-4e21-bb4f-d8f1e4ad3959");
  const fuzzy = ok<EntityRef[]>("POST", "/api/resolve", { name: "aavu", kind: "company" });
  assert.ok(fuzzy.some((e) => e.name === "Aavuus"));
  assert.ok(fuzzy.every((e) => Object.keys(e).sort().join() === "description,id,name,type"));
  assert.deepEqual(ok("POST", "/api/resolve", { name: "zzzz-none", kind: "company" }), []);
  assert.equal(status("POST", "/api/resolve", { name: "Tesi", kind: "fund" }), 422);
  assert.equal(status("POST", "/api/resolve", { kind: "company" }), 422);
});

test("every demo founder report, check and brief is served", () => {
  for (const f of index.founder_mode) {
    const r = ok<FounderReport>("POST", "/api/founder/analyze", { company_id: f.company_id });
    assert.equal(r.company.id, f.company_id);
  }
  for (const c of index.investor_mode) ok("POST", "/api/investor/check", { ...c });
  for (const b of index.briefs) ok("POST", "/api/brief", { ...b });
});

test("alias IDs resolve to the canonical fixture", () => {
  const [alias, canonical] = Object.entries(index.aliases).find(([, c]) =>
    index.founder_mode.some((f) => f.company_id === c),
  )!;
  const r = ok<FounderReport>("POST", "/api/founder/analyze", { company_id: alias });
  assert.equal(r.company.id, canonical);
});

test("unknown entities are 404 with an error message", () => {
  for (const [path, body] of [
    ["/api/founder/analyze", { company_id: "nope" }],
    ["/api/investor/check", { investor_id: "nope", company_id: "nope" }],
    ["/api/brief", { investor_id: "nope", company_id: "nope" }],
  ] as const) {
    const r = api.handle("POST", path, body);
    assert.ok(r.kind === "json" && r.status === 404 && typeof (r.body as { error: string }).error === "string");
  }
  assert.equal(status("GET", "/api/nothing"), 404);
});

test("competitor_ids: removing a competitor drops it and its conflicts", () => {
  const report = ok<FounderReport>("POST", "/api/founder/analyze", {
    company_id: index.founder_mode[0].company_id,
  });
  const keep = new Set(report.competitors.map((c) => c.company.id));
  assert.deepEqual(restrictToCompetitors(report, keep).skip.length, report.skip.length);

  const none = restrictToCompetitors(report, new Set());
  assert.equal(none.competitors.length, 0);
  assert.equal(none.skip.length, 0);
  assert.equal(none.pitch.length, report.pitch.length + report.skip.length);
  for (let i = 1; i < none.pitch.length; i++) {
    assert.ok(none.pitch[i - 1].score >= none.pitch[i].score);
  }
});

test("slush prep: job id, then the recorded stream ending in done", () => {
  const { job_id } = ok<{ job_id: string }>("POST", "/api/slush-prep", {
    company_id: index.founder_mode[0].company_id,
    investor_names: ["Maki.vc"],
  });
  const r = api.handle("GET", `/api/jobs/${job_id}/stream`);
  assert.equal(r.kind, "stream");
  const events = (r as { events: AgentEvent[] }).events;
  assert.equal(events.at(-1)?.type, "done");
  assert.ok(events.some((e) => e.type === "brief" && e.brief));
  assert.equal(status("GET", "/api/jobs/missing/stream"), 404);
  assert.equal(status("POST", "/api/slush-prep", { company_id: "x", investor_names: [] }), 422);
});

test("chat streams text chunks and ends with citations on done", () => {
  const r = api.handle("POST", "/api/chat", { message: "hi" });
  assert.equal(r.kind, "stream");
  const events = (r as { events: AgentEvent[] }).events;
  assert.ok(events.some((e) => e.type === "text"));
  assert.ok((events.at(-1)?.citations.length ?? 0) > 0);
  assert.equal(status("POST", "/api/chat", {}), 422);
});

test("funding fit (mock of B21): only with an amount, every card gets one, bad amounts are 422", () => {
  const company_id = index.founder_mode[0].company_id;
  const plain = ok<FounderReport>("POST", "/api/founder/analyze", { company_id });
  assert.ok([...plain.pitch, ...plain.skip].every((s) => s.funding_fit === null));

  const fit = ok<FounderReport>("POST", "/api/founder/analyze", { company_id, target_amount_eur: 3_000_000 });
  const cards = [...fit.pitch, ...fit.skip];
  assert.ok(cards.length > 0 && cards.every((s) => s.funding_fit !== null));
  const verdicts = new Set(cards.map((s) => s.funding_fit!.verdict));
  assert.ok([...verdicts].every((v) => ["fits", "too_small", "too_large", "unknown"].includes(v)));
  assert.ok(cards.some((s) => s.funding_fit!.verdict !== "unknown"), "some investors have round sizes");

  for (const bad of [0, -5, "3M"]) {
    assert.equal(status("POST", "/api/founder/analyze", { company_id, target_amount_eur: bad }), 422);
  }
  const pair = index.investor_mode[0];
  const check = ok<InvestorCheck>("POST", "/api/investor/check", { ...pair, max_check_eur: 500_000 });
  assert.ok(check.funding_fit && check.funding_fit.text.length > 0);
  assert.equal(ok<InvestorCheck>("POST", "/api/investor/check", { ...pair }).funding_fit, null);
});

test("slush prep: all_slush_investors makes the names optional (B17)", () => {
  const company_id = index.founder_mode[0].company_id;
  assert.equal(status("POST", "/api/slush-prep", { company_id, investor_names: [], all_slush_investors: true }), 200);
  assert.equal(status("POST", "/api/slush-prep", { company_id, all_slush_investors: true }), 200);
  assert.equal(status("POST", "/api/slush-prep", { company_id }), 422);
});
