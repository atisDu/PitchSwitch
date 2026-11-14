import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { citedNumbers, parseInline, parseMarkdown } from "./markdown.ts";
import type { Brief } from "./types.ts";

test("inline: bold, italic, citations, plain text", () => {
  assert.deepEqual(parseInline("**Verdict: skip.** Backs Aavuus [1][2]."), [
    { kind: "bold", children: [{ kind: "text", text: "Verdict: skip." }] },
    { kind: "text", text: " Backs Aavuus " },
    { kind: "cite", n: 1 },
    { kind: "cite", n: 2 },
    { kind: "text", text: "." },
  ]);
  assert.deepEqual(parseInline("an *early* fund"), [
    { kind: "text", text: "an " },
    { kind: "italic", children: [{ kind: "text", text: "early" }] },
    { kind: "text", text: " fund" },
  ]);
  // Not markup: lone asterisks, link-like brackets, HTML stays text.
  assert.deepEqual(parseInline("2 * 3 [a] <b>x</b>"), [{ kind: "text", text: "2 * 3 [a] <b>x</b>" }]);
});

test("blocks: headings, lists, paragraphs, continuation lines", () => {
  const md = "# Title\n\nIntro line one\nline two [3].\n\n## Activity\n- Led A [1].\n- Led B\n  (2026) [2].\n\n1. first\n2. second";
  const blocks = parseMarkdown(md);
  assert.deepEqual(
    blocks.map((b) => b.kind + (b.kind === "heading" ? b.level : "")),
    ["heading1", "paragraph", "heading2", "list", "list"],
  );
  const list = blocks[3];
  assert.ok(list.kind === "list" && !list.ordered && list.items.length === 2);
  assert.deepEqual(list.items[1].at(-1), { kind: "text", text: "." });
  assert.ok(blocks[4].kind === "list" && blocks[4].ordered);
  assert.deepEqual(citedNumbers(blocks), [3, 1, 2]);
});

test("every brief fixture parses and cites only existing citations", () => {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "../../contracts/fixtures/models");
  const files = readdirSync(dir).filter((f) => f.startsWith("brief_"));
  assert.ok(files.length > 0);
  for (const f of files) {
    const brief = JSON.parse(readFileSync(join(dir, f), "utf8")) as Brief;
    const blocks = parseMarkdown(brief.markdown);
    assert.ok(blocks.length > 0, f);
    for (const n of citedNumbers(blocks)) {
      assert.ok(n >= 1 && n <= brief.citations.length, `${f}: [${n}] out of range`);
    }
  }
});
