// Score breakdown (C17, B17): each investor's first reason says how its score adds up, e.g.
// "Score 69.6/100 = leads 25/25 (2 led) + companies here 11.3/15 (2 companies, 2.3 weighted by
// closeness) + ... + Nordic/Baltic 10/10 (Helsinki, from its description)". Parts are split by
// " + " (never inside a part, notes/B.md). Anything else is left as a plain reason.

import type { Reason } from "./types";

export interface ScorePart {
  name: string; // "leads", "companies here", "Nordic/Baltic"
  got: number;
  max: number;
  detail: string | null; // the text in brackets, if any
}

export interface ScoreBreakdown {
  total: number;
  outOf: number;
  parts: ScorePart[];
}

const HEAD = /^Score\s+([\d.]+)\s*\/\s*(\d+)\s*=\s*(.+)$/;
const PART = /^(.+?)\s+([\d.]+)\s*\/\s*([\d.]+)(?:\s*\((.*)\))?\s*$/;

export function parseBreakdown(text: string): ScoreBreakdown | null {
  const head = HEAD.exec(text.trim());
  if (!head) return null;
  const parts: ScorePart[] = [];
  for (const raw of head[3].split(" + ")) {
    const m = PART.exec(raw.trim());
    if (!m) return null; // not the format we know: show the reason as text instead
    parts.push({ name: m[1].trim(), got: Number(m[2]), max: Number(m[3]), detail: m[4]?.trim() || null });
  }
  return parts.length ? { total: Number(head[1]), outOf: Number(head[2]), parts } : null;
}

/** The breakdown (if the first reason is one) and the remaining reasons. */
export function splitReasons(reasons: Reason[]): { breakdown: ScoreBreakdown | null; source: Reason | null; rest: Reason[] } {
  const first = reasons[0];
  const breakdown = first ? parseBreakdown(first.text) : null;
  return breakdown ? { breakdown, source: first, rest: reasons.slice(1) } : { breakdown: null, source: null, rest: reasons };
}
