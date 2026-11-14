// The only module that talks to the backend; components never call fetch directly.
//
// In the browser, requests go to same-origin `/api/*`, which next.config.ts
// rewrites to `${API_URL}/api/*` (B's server, or C's mock on another port).
// On the server (server components, route handlers) we call API_URL directly.

import { parseAgentEvents } from "./sse.ts";
import type {
  AgentEvent,
  Brief,
  BriefRequest,
  ChatRequest,
  EntityKind,
  EntityRef,
  FounderAnalyzeRequest,
  FounderReport,
  HealthResponse,
  InvestorCheck,
  InvestorCheckRequest,
  SlushPrepRequest,
  SlushPrepResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number; // 0 = network error, no response

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function baseUrl(): string {
  if (typeof window !== "undefined") return "";
  return (process.env.API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl()}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Can't reach the PitchSwitch server.", 0);
  }
  if (!res.ok) {
    let message = `Request failed (${res.status}).`;
    try {
      const body = (await res.json()) as { error?: unknown };
      if (typeof body.error === "string" && body.error) message = body.error;
    } catch {
      // not a JSON error body; keep the generic message
    }
    throw new ApiError(message, res.status);
  }
  return res;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await request(path, { signal })).json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await request(path, { method: "POST", body: JSON.stringify(body), signal });
  return res.json() as Promise<T>;
}

async function* stream(res: Response): AsyncGenerator<AgentEvent> {
  if (!res.body) throw new ApiError("The server sent an empty stream.", res.status);
  yield* parseAgentEvents(res.body);
}

// --- Routes (contracts/api.md) -----------------------------------------------

export function health(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson("/api/health", signal);
}

export function resolve(name: string, kind: EntityKind, signal?: AbortSignal): Promise<EntityRef[]> {
  return postJson("/api/resolve", { name, kind }, signal);
}

export function analyzeFounder(
  body: FounderAnalyzeRequest,
  signal?: AbortSignal,
): Promise<FounderReport> {
  return postJson("/api/founder/analyze", body, signal);
}

export function checkInvestor(
  body: InvestorCheckRequest,
  signal?: AbortSignal,
): Promise<InvestorCheck> {
  return postJson("/api/investor/check", body, signal);
}

export function getBrief(body: BriefRequest, signal?: AbortSignal): Promise<Brief> {
  return postJson("/api/brief", body, signal);
}

export function startSlushPrep(
  body: SlushPrepRequest,
  signal?: AbortSignal,
): Promise<SlushPrepResponse> {
  return postJson("/api/slush-prep", body, signal);
}

/** Events of a slush-prep job, in order; ends after the `done` event. */
export async function* jobEvents(jobId: string, signal?: AbortSignal): AsyncGenerator<AgentEvent> {
  const res = await request(`/api/jobs/${encodeURIComponent(jobId)}/stream`, {
    headers: { Accept: "text/event-stream" },
    signal,
  });
  yield* stream(res);
}

/** Streams a chat answer: `text` chunks, then `done` carrying the citations. */
export async function* chat(body: ChatRequest, signal?: AbortSignal): AsyncGenerator<AgentEvent> {
  const res = await request("/api/chat", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { Accept: "text/event-stream" },
    signal,
  });
  yield* stream(res);
}
