import assert from "node:assert/strict";
import { test } from "node:test";

import type { Round } from "../lib/types.ts";
import { fitForCheck, fitForRaise } from "./funding.ts";

const r = (amount: number | null): Round => ({
  id: String(amount),
  company_id: "c",
  label: "Seed",
  date: "2026-01-01",
  amount_text: null,
  amount_eur: amount,
  investors: [],
  sources: [{ name: "x.com", url: null, date: null, rank: "PRESS" }],
});

test("fitForRaise compares the raise with the rounds an investor joins", () => {
  const rounds = [r(1_000_000), r(5_000_000)];
  assert.equal(fitForRaise(3_000_000, "Fund", rounds).verdict, "fits");
  assert.match(fitForRaise(3_000_000, "Fund", rounds).text, /€1M–€5M; your €3M raise fits/);
  assert.equal(fitForRaise(200_000, "Fund", rounds).verdict, "too_small");
  assert.equal(fitForRaise(50_000_000, "Fund", rounds).verdict, "too_large");
  assert.equal(fitForRaise(3_000_000, "Fund", [r(null)]).verdict, "unknown");
  assert.deepEqual(fitForRaise(3_000_000, "Fund", [r(null)]).sources, []);
});

test("fitForCheck compares the check with the company's own rounds", () => {
  const rounds = [r(2_000_000), r(10_000_000)];
  assert.equal(fitForCheck(1_000_000, "Startup", rounds).verdict, "fits");
  assert.equal(fitForCheck(20_000_000, "Startup", rounds).verdict, "too_small");
  assert.equal(fitForCheck(100_000, "Startup", rounds).verdict, "too_large");
  assert.equal(fitForCheck(1_000_000, "Startup", []).verdict, "unknown");
});
