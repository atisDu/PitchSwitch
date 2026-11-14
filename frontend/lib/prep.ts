// Slush prep (C11): pasted names → one card per investor, built by folding the
// job's AgentEvents (contracts/api.md → Streams; notes/B.md → B13).
// Events of different investors interleave; every event about one pasted name
// carries `investor_name` exactly as pasted. The stream replays from the start
// when reopened, so state is always rebuilt from `initialPrep(names)`.

import type { AgentEvent, Brief, EntityRef } from "./types";

export const MAX_NAMES = 25; // the API answers 422 above this

export type CardStatus = "waiting" | "working" | "done" | "error";

export interface PrepCard {
  name: string; // as pasted
  status: CardStatus;
  steps: string[];
  investor: EntityRef | null;
  brief: Brief | null;
  error: string | null;
}

export interface PrepState {
  general: string[]; // steps not tied to one investor
  cards: PrepCard[]; // in paste order; unknown names appended
  errors: string[]; // errors not tied to one investor
  done: boolean;
}

/** Split a pasted list on new lines, commas or semicolons; drop blanks and repeats. */
export function parseNames(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of text.split(/[\n,;]+/)) {
    const name = raw.replace(/^[\s\-*•\d.)]+/, "").trim(); // tolerate pasted bullets / numbering
    const key = name.toLowerCase();
    if (!name || seen.has(key)) continue;
    seen.add(key);
    out.push(name);
  }
  return out;
}

export function initialPrep(names: string[]): PrepState {
  return {
    general: [],
    cards: names.map((name) => ({ name, status: "waiting", steps: [], investor: null, brief: null, error: null })),
    errors: [],
    done: false,
  };
}

export function applyEvent(state: PrepState, e: AgentEvent): PrepState {
  if (e.type === "done") return { ...state, done: true };
  if (!e.investor_name) {
    if (e.type === "error") return { ...state, errors: [...state.errors, e.message ?? "Something failed."] };
    if (e.type === "step" && e.message) return { ...state, general: [...state.general, e.message] };
    return state;
  }

  const key = e.investor_name.trim().toLowerCase();
  let idx = state.cards.findIndex((c) => c.name.toLowerCase() === key);
  let cards = state.cards;
  if (idx === -1) {
    cards = [...cards, { name: e.investor_name, status: "waiting", steps: [], investor: null, brief: null, error: null }];
    idx = cards.length - 1;
  }
  const card = { ...cards[idx] };
  if (e.investor) card.investor = e.investor;
  switch (e.type) {
    case "step":
    case "text":
      if (e.message) card.steps = [...card.steps, e.message];
      if (card.status === "waiting") card.status = "working";
      break;
    case "brief":
      card.brief = e.brief;
      card.status = "done";
      break;
    case "error":
      card.error = e.message ?? "Something failed.";
      card.status = "error";
      break;
  }
  return { ...state, cards: cards.map((c, i) => (i === idx ? card : c)) };
}

/** Cards still open when the stream ended never got an answer. */
export function finish(state: PrepState): PrepState {
  return {
    ...state,
    done: true,
    cards: state.cards.map((c) =>
      c.status === "waiting" || c.status === "working"
        ? { ...c, status: "error", error: c.error ?? "No answer came back for this name." }
        : c,
    ),
  };
}
