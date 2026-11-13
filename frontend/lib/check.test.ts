import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { backersOf, investorConflictText, marketMap, roundTitle, sortRounds } from "./check.ts";
import type { EntityRef, InvestorCheck, Round } from "./types.ts";

const ref = (id: string, type = "Organization"): EntityRef => ({ id, name: id, type, description: null });
const round = (over: Partial<Round>): Round => ({
  id: Math.random().toString(36),
  company_id: "x",
  label: null,
  date: null,
  amount_text: null,
  amount_eur: null,
  investors: [],
  sources: [],
  ...over,
});

test("sortRounds: newest dated first, undated last", () => {
  const rs = [round({ id: "u" }), round({ id: "old", date: "2024" }), round({ id: "new", date: "2026-04-14" })];
  assert.deepEqual(sortRounds(rs).map((r) => r.id), ["new", "old", "u"]);
});

test("backersOf dedupes, a lead anywhere wins, leads first", () => {
  const rs = [
    round({ investors: [{ investor: ref("Tesi"), is_lead: false }, { investor: ref("NIF"), is_lead: true }] }),
    round({ investors: [{ investor: ref("Tesi"), is_lead: null }, { investor: ref("Angel"), is_lead: null }] }),
  ];
  assert.deepEqual(
    backersOf(rs).map((b) => [b.investor.id, b.led]),
    [["NIF", true], ["Angel", false], ["Tesi", false]],
  );
});

test("roundTitle", () => {
  assert.equal(roundTitle(round({})), "Round details unknown");
  assert.equal(roundTitle(round({ label: "Series A" })), "Series A");
  assert.equal(roundTitle(round({ date: "2026" })), "Round");
});

test("investorConflictText", () => {
  const c = { kind: "PORTFOLIO" as const, competitor: ref("Aavuus", "Company"), via_person: null, sources: [] };
  assert.equal(investorConflictText(c, "Stendr"), "Aavuus is in your portfolio and competes with Stendr");
  assert.equal(
    investorConflictText({ ...c, kind: "BOARD", via_person: ref("Jane", "Person") }, "Stendr"),
    "Jane sits on the board of Aavuus, which competes with Stendr",
  );
});

test("marketMap on every investor-check fixture keeps every round", () => {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "../../contracts/fixtures/models");
  const files = readdirSync(dir).filter((f) => f.startsWith("investor_check_"));
  assert.ok(files.length > 0);
  for (const f of files) {
    const check = JSON.parse(readFileSync(join(dir, f), "utf8")) as InvestorCheck;
    const map = marketMap(check);
    assert.equal(map[0].company.id, check.company.id, "startup first");
    assert.equal(map[0].competitor, null);
    assert.equal(
      map.reduce((n, e) => n + e.rounds.length, 0),
      check.rounds.length,
      `${f}: no round dropped`,
    );
  }
});
