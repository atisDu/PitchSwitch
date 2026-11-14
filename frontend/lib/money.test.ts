import assert from "node:assert/strict";
import { test } from "node:test";

import { formatEuro, parseEuro } from "./money.ts";

test("parseEuro reads what people type", () => {
  assert.equal(parseEuro("3M"), 3_000_000);
  assert.equal(parseEuro("€500k"), 500_000);
  assert.equal(parseEuro("3 000 000"), 3_000_000);
  assert.equal(parseEuro("3,000,000"), 3_000_000);
  assert.equal(parseEuro("3.000.000 EUR"), 3_000_000);
  assert.equal(parseEuro("2.5m"), 2_500_000);
  assert.equal(parseEuro("1,2 M"), 1_200_000);
  assert.equal(parseEuro("750000"), 750_000);
  assert.equal(parseEuro("1bn"), 1_000_000_000);
  assert.equal(parseEuro("3 million"), 3_000_000);
  assert.equal(parseEuro("2.5 millions"), 2_500_000);
  assert.equal(parseEuro("500 thousand"), 500_000);
  assert.equal(parseEuro("3 mio €"), 3_000_000);
  assert.equal(parseEuro("1 billion"), 1_000_000_000);
});

test("parseEuro refuses what the API would 422", () => {
  for (const bad of ["", "0", "-3M", "abc", "3M5", "€", "1.2.3k"]) assert.equal(parseEuro(bad), null, bad);
});

test("formatEuro", () => {
  assert.equal(formatEuro(3_000_000), "€3M");
  assert.equal(formatEuro(2_500_000), "€2.5M");
  assert.equal(formatEuro(500_000), "€500k");
  assert.equal(formatEuro(1_000_000_000), "€1B");
  assert.equal(formatEuro(950), "€950");
});
