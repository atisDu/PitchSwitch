// Turn API failures into plain language. The backend sometimes passes Cala's raw error through
// (`data source unavailable: Cala POST /entities/x failed (422): {"response_type":…}`); people
// should see what happened and what to do, with the raw text kept for debugging.

import { ApiError } from "./api.ts";

export interface FriendlyError {
  message: string; // what to show
  notFound: boolean; // retrying won't help
  detail: string | null; // the raw text, for a "Technical details" fold
}

const TECHNICAL = /[{}]|\b(POST|GET)\s+\/|\(\d{3}\)|Traceback|Exception/;

export function describeError(err: unknown): FriendlyError {
  if (!(err instanceof ApiError)) return { message: "Something went wrong.", notFound: false, detail: null };
  const raw = err.message;
  const detail = TECHNICAL.test(raw) ? raw : null;
  if (err.status === 0) return { message: "Can't reach the PitchSwitch server. Check your connection.", notFound: false, detail: null };
  if (err.status === 404 || /\(4(0[04]|22)\)|valid UUID|not a company|not found/i.test(raw)) {
    return {
      message: detail ? "That link doesn't point to a company or investor in Cala." : raw,
      notFound: true,
      detail,
    };
  }
  if (/CACHE_ONLY/i.test(raw)) {
    return { message: "The demo server only answers from its cache right now, and this isn't cached.", notFound: true, detail: raw };
  }
  if (detail || /data source unavailable|cala/i.test(raw) || err.status >= 500) {
    return { message: "Cala, our data source, didn't answer. Try again in a moment.", notFound: false, detail: detail ?? raw };
  }
  return { message: raw, notFound: false, detail: null };
}
