// Does a search result resemble what the user typed? Cala's name search is fuzzy, so
// "Qwxyzz Robotics" returns every "... Robotics" and "Tuomas Rasila" a golf company.
// Shared by the entity picker (close vs looser matches) and Slush prep's "Did you mean".

// Words too common in company and fund names to count as a match on their own.
const GENERIC = new Set([
  "ventures", "venture", "capital", "fund", "funds", "partners", "invest", "investments", "vc",
  "robotics", "technologies", "technology", "tech", "labs", "lab", "ai", "systems", "group",
  "holding", "holdings", "solutions", "company", "international", "global", "the", "and", "of",
  "oy", "oyj", "ab", "as", "asa", "ltd", "limited", "llc", "inc", "gmbh", "sa", "bv", "plc", "ou",
]);

export const INVESTOR_WORDS = /\b(ventur\w*|capital|funds?|invest\w*|partners|angels?|equity|vc)\b/i;

/** A person (angel) or an organisation whose name or description says it invests. */
export function looksLikeInvestor(e: { name: string; type: string; description: string | null }): boolean {
  return e.type === "Person" || INVESTOR_WORDS.test(e.name) || INVESTOR_WORDS.test(e.description ?? "");
}

export const words = (s: string) =>
  s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9 ]+/g, " ").split(/\s+/).filter(Boolean);
const squash = (s: string) => words(s).join("");

/**
 * Shares a distinctive word with the query, or one name starts with the whole other once spaces
 * and punctuation are gone ("Makivc" → "Maki.vc"). A shared prefix alone isn't enough: "NestAI"
 * must not match "NESTII" or "NESTA".
 */
export function resemblesName(query: string, candidate: string): boolean {
  const distinctive = words(query).filter((w) => w.length >= 4 && !GENERIC.has(w));
  const cand = new Set(words(candidate));
  if (distinctive.some((w) => cand.has(w))) return true;
  const q = squash(query);
  const c = squash(candidate);
  return q.length >= 4 && c.length >= 4 && (c.startsWith(q) || q.startsWith(c));
}

/**
 * Results that resemble the query, and the rest (kept, but shown only on request). With
 * `investorsOnly`, a close result that doesn't look like an investor counts as loose too.
 */
export function splitMatches<T extends { name: string; type: string; description: string | null }>(
  query: string,
  items: T[],
  investorsOnly = false,
): { close: T[]; loose: T[] } {
  const close: T[] = [];
  const loose: T[] = [];
  for (const it of items) {
    const ok = resemblesName(query, it.name) && (!investorsOnly || looksLikeInvestor(it));
    (ok ? close : loose).push(it);
  }
  return { close, loose };
}
