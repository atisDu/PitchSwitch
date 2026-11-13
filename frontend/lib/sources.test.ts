import assert from "node:assert/strict";
import { test } from "node:test";

import { formatSourceDate, rankLabel, safeUrl, sortSources } from "./sources.ts";
import type { Source } from "./types.ts";

const src = (rank: Source["rank"], date: string | null, name: string = rank): Source => ({
  name,
  url: null,
  date,
  rank,
});

test("rank labels", () => {
  assert.equal(rankLabel("PRIMARY"), "Primary");
  assert.equal(rankLabel("AGGREGATOR"), "Aggregator");
  assert.equal(rankLabel("UNKNOWN"), "Source");
});

test("partial dates", () => {
  assert.equal(formatSourceDate("2025-10-03"), "3 Oct 2025");
  assert.equal(formatSourceDate("2025-10"), "Oct 2025");
  assert.equal(formatSourceDate("2026"), "2026");
  assert.equal(formatSourceDate("2025-10-03T12:00:00Z"), "3 Oct 2025");
  assert.equal(formatSourceDate("2025-13"), "2025");
  assert.equal(formatSourceDate("last spring"), "last spring");
  assert.equal(formatSourceDate(null), null);
  assert.equal(formatSourceDate(""), null);
});

test("only http(s) urls", () => {
  assert.equal(safeUrl("https://example.com/a"), "https://example.com/a");
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("not a url"), null);
  assert.equal(safeUrl(null), null);
});

test("sorts by rank, then newest", () => {
  const input = [
    src("PRESS", "2024-01", "old press"),
    src("UNKNOWN", null),
    src("PRIMARY", "2023"),
    src("PRESS", "2025-06", "new press"),
    src("AGGREGATOR", "2026"),
  ];
  assert.deepEqual(
    sortSources(input).map((s) => s.name),
    ["PRIMARY", "new press", "old press", "AGGREGATOR", "UNKNOWN"],
  );
  assert.equal(input[0].name, "old press"); // not mutated
});
