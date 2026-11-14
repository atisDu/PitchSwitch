// Small display helpers shared by the report screens.

import { formatSourceDate } from "./sources.ts";

/** "AEROSPACE_AND_DEFENSE" → "Aerospace and defense" */
export function prettyEnum(value: string): string {
  const words = value.toLowerCase().split(/[_\s]+/).filter(Boolean);
  if (words.length === 0) return value;
  const text = words.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Remaining competitor IDs after the user removed some, in report order. */
export function keptCompetitorIds(competitorIds: string[], removed: ReadonlySet<string>): string[] {
  return competitorIds.filter((id) => !removed.has(id));
}

// Legal suffixes keep their usual casing when an all-caps name is softened.
const SUFFIX: Record<string, string> = {
  AS: "AS", AB: "AB", OY: "Oy", OYJ: "Oyj", APS: "ApS", ASA: "ASA", LTD: "Ltd", LLC: "LLC", INC: "Inc",
  PLC: "plc", GMBH: "GmbH", SA: "SA", BV: "BV", OÜ: "OÜ", UK: "UK", VC: "VC", AI: "AI",
  THE: "The", AND: "and", OF: "of", FOR: "for",
};

/**
 * Company registers shout ("STARTUPLAB FOUNDERS AS"); show such names in title case
 * ("Startuplab Founders AS"). Mixed-case names and short acronyms ("IQM") are left alone.
 */
export function displayName(name: string): string {
  if (name !== name.toUpperCase() || !/\p{Lu}{4,}/u.test(name)) return name;
  return name
    .split(/(\s+|-)/)
    .map((w, i) => {
      const known = SUFFIX[w];
      if (known) return i === 0 ? known.charAt(0).toUpperCase() + known.slice(1) : known;
      if (w.length <= 3 || !/\p{Lu}/u.test(w)) return w; // acronyms, separators, numbers
      return w.charAt(0) + w.slice(1).toLowerCase();
    })
    .join("");
}

/** "Skyfall Ventures" → "Skyfall Ventures'", "Maki.vc" → "Maki.vc's". */
export function possessive(name: string): string {
  return /s$/.test(name) ? `${name}'` : `${name}'s`; // "Founders AS" → "AS's"
}

/** ISO dates inside B's sentences ("last lead 2026-06-09") read like the badges: "9 Jun 2026". */
export function prettyDates(text: string): string {
  return text.replace(/\b\d{4}-\d{2}-\d{2}\b/g, (d) => formatSourceDate(d) ?? d);
}

/** An investor's kind as a founder thinks of it: Cala types funds as Company or Organization. */
export function investorKind(type: string): string {
  return type === "Person" ? "Angel" : "Fund";
}
