// Mock API server for frontend work before B's API is live (task C2).
//
//   npm run mock                      # http://localhost:8001
//   API_URL=http://localhost:8001 npm run dev
//
// Env: MOCK_PORT (8001), MOCK_DELAY_MS (400, latency for JSON routes so loading
// states show), MOCK_STEP_MS (350, gap between streamed events).
// Add ?mock_error=<status> to any request to get that error, for error states.

import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { MockApi } from "./handlers.ts";

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURES = process.env.MOCK_FIXTURES ?? join(here, "../../contracts/fixtures/models");
const PORT = Number(process.env.MOCK_PORT ?? 8001);
const DELAY_MS = Number(process.env.MOCK_DELAY_MS ?? 400);
const STEP_MS = Number(process.env.MOCK_STEP_MS ?? 350);

const api = new MockApi(FIXTURES);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type, Accept",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

async function readBody(req: IncomingMessage): Promise<Record<string, unknown> | null> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  if (!raw.trim()) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function sendJson(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { ...CORS, "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

async function handle(req: IncomingMessage, res: ServerResponse) {
  const url = new URL(req.url ?? "/", "http://mock");
  const method = req.method ?? "GET";
  if (method === "OPTIONS") {
    res.writeHead(204, CORS);
    return res.end();
  }

  const forced = Number(url.searchParams.get("mock_error"));
  if (forced >= 400) {
    await sleep(DELAY_MS);
    return sendJson(res, forced, { error: `Mock error ${forced} (requested with ?mock_error).` });
  }

  const body = method === "POST" ? await readBody(req) : {};
  if (body === null) return sendJson(res, 422, { error: "Body must be a JSON object." });

  const result = api.handle(method, url.pathname, body);
  if (result.kind === "json") {
    await sleep(DELAY_MS);
    return sendJson(res, result.status, result.body);
  }

  res.writeHead(200, {
    ...CORS,
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  let closed = false;
  req.on("close", () => (closed = true));
  for (const event of result.events) {
    await sleep(STEP_MS);
    if (closed) return;
    res.write(`data: ${JSON.stringify(event)}\n\n`);
  }
  res.end();
}

createServer((req, res) => {
  handle(req, res).catch((err: unknown) => {
    console.error(err);
    if (!res.headersSent) sendJson(res, 500, { error: "Mock server error." });
    else res.end();
  });
}).listen(PORT, () => {
  console.log(`PitchSwitch mock API on http://localhost:${PORT} (fixtures: ${FIXTURES})`);
});
