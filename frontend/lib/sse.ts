// Parser for the contract's SSE wire format (contracts/api.md → Streams):
// one `data: <AgentEvent JSON>\n\n` per event, no named events, no ids.
// Works on any byte stream, so it serves both GET streams and POST /api/chat.

import type { AgentEvent } from "./types";

export async function* parseAgentEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<AgentEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (value) buffer += decoder.decode(value, { stream: true });
      if (done) buffer += decoder.decode();
      // A trailing "\r" may be half of a "\r\n" split across chunks: keep it until done.
      buffer = buffer.replace(done ? /\r\n?/g : /\r\n|\r(?!$)/g, "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const event = parseBlock(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (event) {
          yield event;
          if (event.type === "done") return;
        }
      }
      if (done) {
        const event = parseBlock(buffer);
        if (event) yield event;
        return;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// One SSE block → event. Multi-line `data:` fields are joined with "\n" per the
// SSE spec; comment lines (":") and other fields are ignored.
function parseBlock(block: string): AgentEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""));
  if (data.length === 0) return null;
  return JSON.parse(data.join("\n")) as AgentEvent;
}
