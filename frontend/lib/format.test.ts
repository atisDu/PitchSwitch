import assert from "node:assert/strict";
import { test } from "node:test";

import { displayName, investorKind, keptCompetitorIds, possessive, prettyDates, prettyEnum } from "./format.ts";

test("prettyEnum", () => {
  assert.equal(prettyEnum("AEROSPACE_AND_DEFENSE"), "Aerospace and defense");
  assert.equal(prettyEnum("FINTECH"), "Fintech");
  assert.equal(prettyEnum(""), "");
});

test("keptCompetitorIds keeps order and drops removed", () => {
  assert.deepEqual(keptCompetitorIds(["a", "b", "c"], new Set(["b"])), ["a", "c"]);
  assert.deepEqual(keptCompetitorIds(["a"], new Set()), ["a"]);
  assert.deepEqual(keptCompetitorIds(["a"], new Set(["a"])), []);
});

test("displayName softens all-caps register names only", () => {
  assert.equal(displayName("STARTUPLAB FOUNDERS AS"), "Startuplab Founders AS");
  assert.equal(displayName("DIANA UK ENTERPRISES LTD"), "Diana UK Enterprises Ltd");
  assert.equal(displayName("THE LEMONADE STAND LTD"), "The Lemonade Stand Ltd");
  assert.equal(displayName("MYDEFENCE GROUP APS"), "Mydefence Group ApS");
  assert.equal(displayName("SMARTCAP"), "Smartcap");
  assert.equal(displayName("IQM"), "IQM");
  assert.equal(displayName("Maki.vc"), "Maki.vc");
  assert.equal(displayName("Sensofusion Oy"), "Sensofusion Oy");
});

test("possessive, dates, kinds", () => {
  assert.equal(possessive("Skyfall Ventures"), "Skyfall Ventures'");
  assert.equal(possessive("Maki.vc"), "Maki.vc's");
  assert.equal(possessive("Startuplab Founders AS"), "Startuplab Founders AS's");
  assert.equal(prettyDates("recency 15/15 (last lead here 2026-06-09)"), "recency 15/15 (last lead here 9 Jun 2026)");
  assert.equal(prettyDates("no dates"), "no dates");
  assert.equal(investorKind("Organization"), "Fund");
  assert.equal(investorKind("Company"), "Fund");
  assert.equal(investorKind("Person"), "Angel");
});
