// Pure helpers behind the source badge (no React, so they're unit-tested).

import type { Source, SourceRank } from "./types";

const RANK_LABEL: Record<SourceRank, string> = {
  PRIMARY: "Primary",
  FILING: "Filing",
  PRESS: "Press",
  AGGREGATOR: "Aggregator",
  UNKNOWN: "Source",
};

// Most reliable first; OVERVIEW: "prefer primary sources when facts conflict".
const RANK_ORDER: SourceRank[] = ["PRIMARY", "FILING", "PRESS", "AGGREGATOR", "UNKNOWN"];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function rankLabel(rank: SourceRank): string {
  return RANK_LABEL[rank] ?? RANK_LABEL.UNKNOWN;
}

/** "2025-10-03" → "3 Oct 2025", "2025-10" → "Oct 2025", "2026" → "2026"; anything else as-is. */
export function formatSourceDate(date: string | null): string | null {
  if (!date) return null;
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?/.exec(date.trim());
  if (!m) return date;
  const [, y, mo, d] = m;
  const month = mo ? MONTHS[Number(mo) - 1] : undefined;
  if (!month) return y; // no month, or an invalid one
  return d ? `${Number(d)} ${month} ${y}` : `${month} ${y}`;
}

/** Only http(s) links are rendered; anything else is shown as plain text. */
export function safeUrl(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** Best rank first, then newest first. Stable for equal keys; does not mutate. */
export function sortSources(sources: Source[]): Source[] {
  return [...sources].sort((a, b) => {
    const r = RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank);
    if (r !== 0) return r;
    return (b.date ?? "").localeCompare(a.date ?? "");
  });
}
