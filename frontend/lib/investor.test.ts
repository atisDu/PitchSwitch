import assert from "node:assert/strict";
import { test } from "node:test";

import { activitySummary, conflictText, leadSummary, skipCause } from "./investor.ts";
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

const sref = (id: string, name: string): EntityRef => ({ id, name, type: "Organization", description: null });
const sanction = (id: string, name: string): Conflict => ({ kind: "SANCTION", competitor: sref(id, name), via_person: null, sources: [] });

test("a sanctions conflict names the fund itself or its LP, never a competitor", () => {
  assert.equal(conflictText(sanction("f1", "Fund One"), "f1"), "Has a sanctions record in Cala");
  assert.equal(conflictText(sanction("lp", "Big LP"), "f1"), "Its LP Big LP has a sanctions record in Cala");
  assert.equal(conflictText(sanction("lp", "Big LP")), "Sanctions record in Cala on Big LP");
});

test("skipCause says what put the funds on Skip", () => {
  const score = (conflicts: Conflict[]) => ({ conflicts }) as unknown as InvestorScore;
  const rival: Conflict = { kind: "PORTFOLIO", competitor: sref("c", "Rival"), via_person: null, sources: [] };
  assert.equal(skipCause([score([rival])]), "backed a direct competitor");
  assert.equal(
    skipCause([score([rival]), score([sanction("f", "F")])]),
    "backed a direct competitor or have a sanctions record in Cala",
  );
});
