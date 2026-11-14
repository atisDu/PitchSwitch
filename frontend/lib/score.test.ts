import assert from "node:assert/strict";
import { test } from "node:test";

import { parseBreakdown, splitReasons } from "./score.ts";

// B's live line for Maki.vc on Sensofusion (B19, 14 Nov).
const MAKI =
  "Score 69.6/100 = leads 25/25 (2 led) + companies here 11.3/15 (2 companies, 2.3 weighted by closeness) + recency 15/15 (last lead here 2026-06-09) + activity 8.3/10 (5 in 12 mo) + warm paths 0/15 (0) + stage fit 0/10 (startup stage unknown) + Nordic/Baltic 10/10 (Helsinki, from its description)";

test("parses B's breakdown line into parts", () => {
  const b = parseBreakdown(MAKI)!;
  assert.equal(b.total, 69.6);
  assert.equal(b.outOf, 100);
  assert.equal(b.parts.length, 7);
  assert.deepEqual(b.parts[0], { name: "leads", got: 25, max: 25, detail: "2 led" });
  assert.deepEqual(b.parts[1], { name: "companies here", got: 11.3, max: 15, detail: "2 companies, 2.3 weighted by closeness" });
  assert.deepEqual(b.parts[6], { name: "Nordic/Baltic", got: 10, max: 10, detail: "Helsinki, from its description" });
  assert.equal(b.parts.reduce((n, p) => n + p.max, 0), 100);
});

test("older and simpler lines parse; anything else is not a breakdown", () => {
  const b17 = parseBreakdown("Score 73.3/100 = leads in this space 35/35 (2 led) + rounds in this space 13.3/20 (2) + recency 25/25 (last lead 2026-06-09) + warm paths 0/20 (0)")!;
  assert.equal(b17.parts.length, 4);
  assert.equal(parseBreakdown("Score 5/100 = warm paths 5/20")!.parts[0].detail, null);
  assert.equal(parseBreakdown("Led Aavuus's Pre-Seed round (2026-06-09)"), null);
  assert.equal(parseBreakdown("Score 5/100 = something odd"), null);
});

test("splitReasons takes the breakdown off the reasons", () => {
  const src = [{ name: "x", url: null, date: null, rank: "PRIMARY" as const }];
  const s = splitReasons([{ text: MAKI, sources: src }, { text: "Led Aavuus", sources: [] }]);
  assert.ok(s.breakdown);
  assert.equal(s.rest.length, 1);
  assert.equal(s.source?.sources.length, 1);
  assert.equal(splitReasons([{ text: "Led Aavuus", sources: [] }]).breakdown, null);
});
