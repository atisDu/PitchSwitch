import assert from "node:assert/strict";
import { test } from "node:test";

import { resemblesName, splitMatches } from "./match.ts";

test("resemblesName", () => {
  assert.equal(resemblesName("Sensofusion", "Sensofusion Oy"), true);
  assert.equal(resemblesName("Sensofusion", "Sensolution AB"), false, "a shared prefix isn't enough");
  assert.equal(resemblesName("NestAI", "NESTII CIC"), false);
  assert.equal(resemblesName("NestAI", "NESTAI LIMITED"), true);
  assert.equal(resemblesName("Maki.vc Fund", "Maki.vc"), true);
  assert.equal(resemblesName("Qwxyzz Robotics", "Deus Robotics"), false, "only a generic word");
  assert.equal(resemblesName("Makivc", "Maki.vc"), true);
  assert.equal(resemblesName("Tuomas Rasila", "RASILA LTD"), true);
  assert.equal(resemblesName("Nonexistent Capital", "Entree Capital"), false);
  assert.equal(resemblesName("Kelluu", "CELLUX"), false);
});

test("splitMatches keeps order and loses nothing", () => {
  const co = (name: string, description: string | null = null) => ({ name, type: "Company", description });
  const items = [co("Deus Robotics"), co("Qwxyzz Robotics Oy"), co("THEKER Robotics")];
  const { close, loose } = splitMatches("Qwxyzz Robotics", items);
  assert.deepEqual(close.map((x) => x.name), ["Qwxyzz Robotics Oy"]);
  assert.deepEqual(loose.map((x) => x.name), ["Deus Robotics", "THEKER Robotics"]);
});

test("splitMatches for a fund: non-investors fold away", () => {
  const items = [
    { name: "Tesi", type: "Organization", description: "Finnish public investment company that provides venture capital" },
    { name: "TESI", type: "Company", description: "Italian construction and engineering consulting firm" },
    { name: "TESI FRANCE", type: "Company", description: "French software and consulting company" },
  ];
  const { close, loose } = splitMatches("Tesi", items, true);
  assert.deepEqual(close.map((x) => x.description?.slice(0, 7)), ["Finnish"]);
  assert.equal(loose.length, 2);
  assert.equal(splitMatches("Tesi", items).close.length, 3, "for a company every Tesi is close");
});
