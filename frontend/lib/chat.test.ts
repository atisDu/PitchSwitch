import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { applyChatEvent, emptyAnswer, joinChunk } from "./chat.ts";
import type { AgentEvent } from "./types.ts";

test("joinChunk: word pieces keep their spacing; whole sentences get one space", () => {
  assert.equal(joinChunk("Joined Kova Labs's Pre-Seed round ", "(2026-11-04) [1]."), "Joined Kova Labs's Pre-Seed round (2026-11-04) [1].");
  assert.equal(joinChunk("No, it backs Stendr [1][2].", "Pitch Maki.vc instead [3]."), "No, it backs Stendr [1][2]. Pitch Maki.vc instead [3].");
  assert.equal(joinChunk("It led €15M.", "NIF led it."), "It led €15M. NIF led it.");
  assert.equal(joinChunk("A [1]", "."), "A [1].");
  assert.equal(joinChunk("", "First."), "First.");
});

test("the recorded chat stream folds into one cited answer", () => {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "../../contracts/fixtures/models");
  const events = JSON.parse(readFileSync(join(dir, "agent_events_chat.json"), "utf8")) as AgentEvent[];
  const a = events.reduce(applyChatEvent, emptyAnswer());
  assert.ok(a.done);
  assert.equal(a.steps.length, 2);
  assert.equal(
    a.text,
    "Joined Kova Labs's Pre-Seed round (2026-11-04) [1][2]. Conflict: Lifeline Ventures AB is tied to your competitor Kova Labs [2][1].",
  );
  for (const n of a.text.matchAll(/\[(\d+)\]/g)) {
    assert.ok(Number(n[1]) <= a.citations.length, "every [n] has a citation");
  }
});
