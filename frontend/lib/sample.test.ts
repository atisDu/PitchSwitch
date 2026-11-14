import assert from "node:assert/strict";
import { test } from "node:test";

import { SAMPLE_COMPANY_ID, isSample, sampleBrief, sampleCheck, sampleReport } from "./sample.ts";
import { parseBreakdown } from "./score.ts";

test("the sample report matches the landing page: 9 to skip, 26 to pitch, sorted, Skip only with conflicts", () => {
  const r = sampleReport();
  assert.equal(r.company.id, SAMPLE_COMPANY_ID);
  assert.equal(r.skip.length, 9);
  assert.equal(r.pitch.length, 26);
  assert.equal(r.pitch[0].investor.name, "Kaamos Ventures");
  assert.ok(r.skip.every((s) => s.conflicts.length > 0) && r.pitch.every((s) => s.conflicts.length === 0));
  for (const list of [r.pitch, r.skip]) assert.deepEqual(list.map((s) => s.score), [...list.map((s) => s.score)].sort((a, b) => b - a));
});

test("every sample score parses as a breakdown whose parts add up to it", () => {
  const r = sampleReport();
  for (const s of [...r.pitch, ...r.skip]) {
    const b = parseBreakdown(s.reasons[0].text);
    assert.ok(b, s.reasons[0].text);
    const sum = b.parts.reduce((t, p) => t + p.got, 0);
    assert.ok(Math.abs(sum - s.score) < 0.15 && b.parts.every((p) => p.got <= p.max), s.investor.name);
  }
});

test("removing a competitor moves its backers to Pitch", () => {
  const all = sampleReport();
  const kept = all.competitors.filter((c) => c.company.name !== "Hjelmvik").map((c) => c.company.id);
  const r = sampleReport(kept);
  assert.equal(r.skip.length, 6);
  assert.ok(r.pitch.some((s) => s.investor.name === "Fjordline Ventures"));
});

test("checks and briefs exist for every sample fund, with valid citation numbers", () => {
  const r = sampleReport();
  for (const s of [...r.pitch, ...r.skip]) {
    assert.ok(isSample(s.investor.id));
    assert.equal(sampleCheck(s.investor.id)?.conflicts.length, s.conflicts.length);
    const brief = sampleBrief(s.investor.id)!;
    const marks = [...brief.markdown.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1]));
    assert.ok(marks.length > 0 && marks.every((n) => n >= 1 && n <= brief.citations.length), s.investor.name);
  }
  assert.equal(sampleBrief("sample-nobody"), null);
});
