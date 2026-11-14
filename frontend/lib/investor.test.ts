import assert from "node:assert/strict";
import { test } from "node:test";

import { activitySummary, conflictText, leadSummary } from "./investor.ts";
import type { Conflict, EntityRef, InvestorScore } from "./types.ts";

const ref = (name: string, type = "Organization"): EntityRef => ({
  id: name.toLowerCase(),
  name,
  type,
  description: null,
});

const score = (over: Partial<InvestorScore>): InvestorScore => ({
  investor: ref("Maki.vc"),
  score: 50,
  conflicts: [],
  leads_in_space: 0,
  rounds_in_space: 0,
  lead_data: "unknown",
  last_lead_date: null,
  deals_last_12m: null,
  warm_paths: [],
  reasons: [],
  funding_fit: null,
  ...over,
});

test("leadSummary follows lead_data", () => {
  assert.equal(
    leadSummary(score({ leads_in_space: 2, rounds_in_space: 2, lead_data: "known" })),
    "Led 2 of 2 rounds in your space",
  );
  assert.equal(
    leadSummary(score({ leads_in_space: 0, rounds_in_space: 1, lead_data: "known" })),
    "In 1 round in your space, none led",
  );
  assert.equal(
    leadSummary(score({ leads_in_space: 1, rounds_in_space: 4, lead_data: "partial" })),
    "Led at least 1 of 4 rounds in your space (lead known for some)",
  );
  assert.equal(
    leadSummary(score({ rounds_in_space: 3, lead_data: "unknown" })),
    "In 3 rounds in your space · Cala doesn't say who led",
  );
  assert.equal(leadSummary(score({})), "No rounds in your space yet");
});

test("activitySummary skips unknowns", () => {
  assert.equal(
    activitySummary(score({ last_lead_date: "2026-06-09", deals_last_12m: 5 })),
    "Last lead 9 Jun 2026 · 5 deals in the last 12 months",
  );
  assert.equal(activitySummary(score({ deals_last_12m: 1 })), "No lead on record · 1 deal in the last 12 months");
  assert.equal(activitySummary(score({})), "No lead on record");
});

test("conflictText", () => {
  const base: Conflict = { kind: "PORTFOLIO", competitor: ref("Kova Labs", "Company"), via_person: null, sources: [] };
  assert.equal(conflictText(base), "Backed your competitor Kova Labs");
  assert.equal(
    conflictText({ ...base, kind: "BOARD", via_person: ref("Jane Doe", "Person") }),
    "Jane Doe sits on the board of your competitor Kova Labs",
  );
  assert.equal(
    conflictText({ ...base, kind: "BOARD" }),
    "Has a seat on the board of your competitor Kova Labs",
  );
});
