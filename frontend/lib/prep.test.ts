import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { applyEvent, finish, initialPrep, investorSuggestions, needsInvestorSuffix, parseNames } from "./prep.ts";
import type { AgentEvent } from "./types.ts";

const ev = (over: Partial<AgentEvent> & Pick<AgentEvent, "type">): AgentEvent => ({
  message: null,
  brief: null,
  investor_name: null,
  investor: null,
  citations: [],
  ...over,
});

test("parseNames: lines, commas, bullets, numbering, blanks, repeats", () => {
  assert.deepEqual(parseNames("Maki.vc\n- Inventure,  Tesi;\n\n2. NATO Innovation Fund\nmaki.vc\n• Lifeline"), [
    "Maki.vc",
    "Inventure",
    "Tesi",
    "NATO Innovation Fund",
    "Lifeline",
  ]);
  assert.deepEqual(parseNames("  \n , ;"), []);
});

test("interleaved events land on the right card; general steps stay general", () => {
  let s = initialPrep(["Maki.vc", "Rainfall Ventures", "Nope Capital"]);
  const found = { id: "r1", name: "Rainfall Ventures", type: "Organization", description: null };
  for (const e of [
    ev({ type: "step", message: "Finding Sensofusion's direct competitors" }),
    ev({ type: "step", investor_name: "Maki.vc", message: "Looking up Maki.vc" }),
    ev({ type: "step", investor_name: "Rainfall Ventures", message: "Looking up Rainfall" }),
    ev({ type: "step", investor_name: "Rainfall Ventures", investor: found, message: "Found" }),
    ev({ type: "error", investor_name: "Nope Capital", message: "No investor named Nope Capital" }),
    ev({
      type: "brief",
      investor_name: "Rainfall Ventures",
      investor: found,
      brief: { investor_id: "r1", company_id: "c", markdown: "## Verdict\n\nSkip [1].", citations: [] },
    }),
  ]) s = applyEvent(s, e);

  assert.deepEqual(s.general, ["Finding Sensofusion's direct competitors"]);
  assert.deepEqual(s.cards.map((c) => c.status), ["working", "done", "error"]);
  assert.equal(s.cards[1].investor?.id, "r1");
  assert.equal(s.cards[1].steps.length, 2);
  assert.equal(s.cards[2].error, "No investor named Nope Capital");

  s = finish(applyEvent(s, ev({ type: "done" })));
  assert.ok(s.done);
  assert.equal(s.cards[0].status, "error", "a card with no answer is closed as failed");
});

test("names the job reports that weren't pasted are appended; matching ignores case", () => {
  let s = initialPrep(["maki.vc"]);
  s = applyEvent(s, ev({ type: "step", investor_name: "Maki.vc", message: "x" }));
  s = applyEvent(s, ev({ type: "step", investor_name: "Extra Fund", message: "y" }));
  assert.deepEqual(s.cards.map((c) => c.name), ["maki.vc", "Extra Fund"]);
});

test("the recorded slush-prep stream folds into one card per pasted name", () => {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "../../contracts/fixtures/models");
  const index = JSON.parse(readFileSync(join(dir, "index.json"), "utf8")) as {
    slush_prep: { investor_names: string[] };
  };
  const events = JSON.parse(readFileSync(join(dir, "agent_events_slush_prep.json"), "utf8")) as AgentEvent[];
  const s = finish(events.reduce(applyEvent, initialPrep(index.slush_prep.investor_names)));
  assert.equal(s.cards.length, index.slush_prep.investor_names.length);
  assert.ok(s.cards.every((c) => c.status === "done" || c.status === "error"));
  assert.ok(s.cards.some((c) => c.brief));
  assert.ok(s.cards.some((c) => c.error));
});

const e = (name: string, type: string, description: string | null, id = name) => ({ id, name, type, description });

test("suggestions: only investor-like entities that resemble the typed name", () => {
  // Live results from /api/resolve, 14 Nov.
  const lifeline = [
    e("Lifeline Ventures AB", "Company", "A Swedish company incorporated in 2010"),
    e("LIFELINE PLC", "Company", "British healthcare provider company"),
    e("Lifeline Ventures", "Organization", "Finnish venture capital firm headquartered in Helsinki"),
    e("Lifeline Ventures Fund II Ky", "Company", "Finnish venture capital fund based in Helsinki"),
  ];
  assert.deepEqual(investorSuggestions("Lifeline", lifeline).map((x) => x.name), [
    "Lifeline Ventures",
    "Lifeline Ventures Fund II Ky",
    "Lifeline Ventures AB",
  ]);
  const rasila = [
    e("Tuomas Grönman Oy", "Company", "A Finnish company founded in 2010"),
    e("Tuomas Seppälä Golf Oy", "Company", "A Finnish golf company"),
    e("RASILA LTD", "Company", "A British construction company"),
  ];
  assert.deepEqual(investorSuggestions("Tuomas Rasila", rasila), []);
  const nonexistent = [
    e("Entree Capital", "Company", "Israel and US-based venture capital firm"),
    e("Notable Capital", "Company", "Venture capital firm"),
  ];
  assert.deepEqual(investorSuggestions("Nonexistent Capital", nonexistent), [], "sharing only 'Capital' isn't a match");
  const maki = [e("Maki.vc", "Company", "Helsinki-based venture capital firm"), e("MAKILA INVEST", "Company", "French company")];
  assert.deepEqual(investorSuggestions("Makivc", maki).map((x) => x.name), ["Maki.vc"]);
  assert.deepEqual(investorSuggestions("Jane Angel", [e("Jane Angel", "Person", null)]).map((x) => x.type), ["Person"]);
});

test("suggestions: dedupe and limit", () => {
  const hits = [e("A Ventures", "Company", null, "1"), e("A Ventures", "Company", null, "1"), e("A Ventures 2", "Company", null, "2")];
  assert.equal(investorSuggestions("A Ventures", hits, 1).length, 1);
  assert.equal(investorSuggestions("A Ventures", hits).length, 2);
});

test("needsInvestorSuffix", () => {
  assert.equal(needsInvestorSuffix("Lifeline"), true);
  assert.equal(needsInvestorSuffix("Lifeline Ventures"), false);
  assert.equal(needsInvestorSuffix("Inventure"), true);
  assert.equal(needsInvestorSuffix("Maki.vc"), false);
});
