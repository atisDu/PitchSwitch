import assert from "node:assert/strict";
import { test } from "node:test";

import { keptCompetitorIds, prettyEnum } from "./format.ts";

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
