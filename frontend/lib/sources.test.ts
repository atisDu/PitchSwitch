import assert from "node:assert/strict";
import { test } from "node:test";

import { dedupeSources, displayRank, formatSourceDate, publisher, rankLabel, safeUrl, sortSources } from "./sources.ts";
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
  assert.equal(rankLabel("UNKNOWN"), "Unrated");
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

const at = (url: string | null, rank: Source["rank"] = "UNKNOWN", date: string | null = "2026-08-24", name = "x"): Source => ({
  name,
  url,
  date,
  rank,
});

test("unranked funding databases show as aggregators; others stay unrated", () => {
  assert.equal(displayRank(at("https://tracxn.com/d/companies/stendr")), "AGGREGATOR");
  assert.equal(displayRank(at("https://www.crunchbase.com/organization/x")), "AGGREGATOR");
  assert.equal(displayRank(at("https://stendr.com/news")), "UNKNOWN");
  assert.equal(displayRank(at(null)), "UNKNOWN");
  assert.equal(displayRank(at("https://tracxn.com/x", "PRESS")), "PRESS"); // Cala's rank wins
});

test("publisher is the website, else a short name", () => {
  assert.equal(publisher(at("https://www.crunchbase.com/a")), "crunchbase.com");
  assert.equal(publisher(at(null, "UNKNOWN", null, "Portfolio")), "Portfolio");
  assert.equal(
    publisher(at(null, "UNKNOWN", null, "SKAALA INVESTMENTS OÜ (11168790) - Overview @ Inforegister.ee")),
    "SKAALA INVESTMENTS OÜ (11168790…",
  );
});

test("dedupe folds one publisher on one date", () => {
  const out = dedupeSources([
    at("https://www.crunchbase.com/a"),
    at("https://stendr.com/news", "UNKNOWN", "2026-04-15"),
    at("https://www.crunchbase.com/b"),
    at("https://pitchbook.com/p"),
  ]);
  assert.deepEqual(
    out.map((e) => [publisher(e.source), e.count]),
    [["crunchbase.com", 2], ["pitchbook.com", 1], ["stendr.com", 1]],
  );
});
