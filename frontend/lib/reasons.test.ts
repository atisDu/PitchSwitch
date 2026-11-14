import assert from "node:assert/strict";
import { test } from "node:test";

import { cardReasons, hiddenFor } from "./reasons.ts";

const r = (text: string) => ({ text, sources: [] });

// B's live lines (deployed API, Sensofusion, 14 Nov).
const PARTNER =
  "Partner for your space: Paavo Räisänen. An interview with Paavo Räisänen confirms his position as a partner at Maki.vc.";
const FRESH = "Fresh fund: Lakestar reported that it closed its Resilience I fund on 17 July 2026, raising €262.2 million.";
const HIDDEN =
  "Hidden conflict: backs Zvook, a direct rival not on your competitor list (Both companies develop drone detection systems for defense and airspace security customers.)";

test("partner, fresh fund and hidden rival leave the plain reasons", () => {
  const c = cardReasons([r("Led 2 rounds"), r(PARTNER), r(FRESH), r(HIDDEN), r("screened: no sanctions record in Cala")]);
  assert.equal(c.partner?.name, "Paavo Räisänen");
  assert.match(c.partner?.claim ?? "", /^An interview/);
  assert.match(c.freshFund?.text ?? "", /^Lakestar reported/);
  assert.equal(c.hidden[0].name, "Zvook");
  assert.match(c.hidden[0].why ?? "", /^Both companies/);
  assert.deepEqual(c.rest.map((x) => x.text), ["Led 2 rounds", "screened: no sanctions record in Cala"]);
});

test("a partner name with an initial stays whole", () => {
  assert.equal(cardReasons([r("Partner for your space: J. Smith. Leads defence deals.")]).partner?.name, "J. Smith");
});

test("conflict restatements are dropped; hidden rivals match by name", () => {
  const c = cardReasons([r("Conflict: its partner X sits on the board of Y, a direct competitor"), r(HIDDEN)]);
  assert.equal(c.rest.length, 0);
  assert.equal(hiddenFor(c.hidden, "ZVOOK")?.name, "Zvook");
  assert.equal(hiddenFor(c.hidden, "Stendr"), null);
});
