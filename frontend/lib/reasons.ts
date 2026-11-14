// B's reason lines with a fixed prefix (notes/B.md, B22-B25) get their own place on a card; the rest
// stay plain reasons. Pure, so the prefixes are unit-tested against B's live wording.

import type { Reason } from "./types";

export interface Partner {
  name: string; // "Paavo Räisänen"
  claim: string; // the sourced sentence(s) after the name
  sources: Reason["sources"];
}

export interface HiddenRival {
  name: string; // the rival as B names it, e.g. "Zvook"
  why: string | null; // the judge's one line, from the brackets
  sources: Reason["sources"];
}

export interface CardReasons {
  partner: Partner | null; // B23 "Partner for your space: <name>. <claim>"
  freshFund: Reason | null; // B23 "Fresh fund: <claim>", prefix removed
  hidden: HiddenRival[]; // B22 "Hidden conflict: backs <X>, a direct rival not on your competitor list (<why>)"
  rest: Reason[]; // everything else, in B's order (conflict restatements dropped)
}

// The name ends at the first ". " that follows two non-dot characters, so "J. Smith. Claim" keeps "J. Smith".
const PARTNER = /^Partner for your space:\s*(.+?[^\s.]{2})\.\s+([\s\S]+)$/;
const HIDDEN = /^Hidden conflict:\s*backs (.+?), a direct rival not on your competitor list(?:\s*\(([\s\S]*)\))?\.?\s*$/;

export function cardReasons(reasons: Reason[]): CardReasons {
  const out: CardReasons = { partner: null, freshFund: null, hidden: [], rest: [] };
  for (const r of reasons) {
    const p = out.partner ? null : PARTNER.exec(r.text);
    if (p) {
      out.partner = { name: p[1].trim(), claim: p[2].trim(), sources: r.sources };
      continue;
    }
    if (!out.freshFund && r.text.startsWith("Fresh fund: ")) {
      out.freshFund = { text: r.text.slice("Fresh fund: ".length), sources: r.sources };
      continue;
    }
    const h = HIDDEN.exec(r.text);
    if (h) {
      out.hidden.push({ name: h[1].trim(), why: h[2]?.trim() || null, sources: r.sources });
      continue;
    }
    // "Conflict: ..." restates a conflict the card already shows with its sources.
    if (r.text.startsWith("Conflict: ")) continue;
    out.rest.push(r);
  }
  return out;
}

/** The hidden-rival line for a conflict, matched by the competitor's name (B gives no ID there). */
export function hiddenFor(hidden: HiddenRival[], competitorName: string): HiddenRival | null {
  const n = competitorName.trim().toLowerCase();
  return hidden.find((h) => h.name.toLowerCase() === n) ?? null;
}
