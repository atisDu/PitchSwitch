import assert from "node:assert/strict";
import { test } from "node:test";

import { parseAgentEvents } from "./sse.ts";
import type { AgentEvent } from "./types.ts";

function ev(partial: Partial<AgentEvent> & Pick<AgentEvent, "type">): AgentEvent {
  return {
    message: null,
    brief: null,
    investor_name: null,
    investor: null,
    citations: [],
    ...partial,
  };
}

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

async function collect(chunks: string[]): Promise<AgentEvent[]> {
  const out: AgentEvent[] = [];
  for await (const e of parseAgentEvents(streamOf(chunks))) out.push(e);
  return out;
}

const step = ev({ type: "step", message: "resolve_company(Kelluu)" });
const text = ev({ type: "text", message: "NATO Innovation Fund led [1]." });
const done = ev({
  type: "done",
  citations: [{ name: "Press", url: "https://example.com", date: "2025-10", rank: "PRESS" }],
});

test("parses one event per data block, in order", async () => {
  const wire = [step, text, done].map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  assert.deepEqual(await collect([wire]), [step, text, done]);
});

test("handles events split across chunks", async () => {
  const wire = `data: ${JSON.stringify(step)}\n\ndata: ${JSON.stringify(done)}\n\n`;
  const chunks: string[] = [];
  for (let i = 0; i < wire.length; i += 7) chunks.push(wire.slice(i, i + 7));
  assert.deepEqual(await collect(chunks), [step, done]);
});

test("stops after done, ignores comments and CRLF", async () => {
  const wire =
    `: keep-alive\r\n\r\n` +
    `data: ${JSON.stringify(step)}\r\n\r\n` +
    `data: ${JSON.stringify(done)}\r\n\r\n` +
    `data: ${JSON.stringify(text)}\r\n\r\n`;
  assert.deepEqual(await collect([wire]), [step, done]);
});

test("flushes a final event without a trailing blank line", async () => {
  assert.deepEqual(await collect([`data: ${JSON.stringify(done)}`]), [done]);
});

test("handles a CRLF split across chunks", async () => {
  const wire = `data: ${JSON.stringify(step)}\r\n\r\ndata: ${JSON.stringify(done)}\r\n\r\n`;
  const cut = wire.indexOf("\r\n") + 1;
  assert.deepEqual(await collect([wire.slice(0, cut), wire.slice(cut)]), [step, done]);
});
