// Pure helpers behind the source badge (no React, so they're unit-tested).

import type { Source, SourceRank } from "./types";

const RANK_LABEL: Record<SourceRank, string> = {
  PRIMARY: "Primary",
  FILING: "Filing",
  PRESS: "Press",
  AGGREGATOR: "Aggregator",
  UNKNOWN: "Unrated",
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

// Cala leaves these databases unranked (UNKNOWN); they are aggregators by definition, so the badge
// says so instead of "Unrated". Display only: the Source itself is passed on unchanged.
const AGGREGATOR_HOSTS = [
  "tracxn.com", "pitchbook.com", "crunchbase.com", "dealroom.co", "cbinsights.com",
  "owler.com", "zoominfo.com", "growjo.com", "f6s.com", "craft.co", "golden.com",
];

const hostOf = (url: string | null): string | null => {
  const href = safeUrl(url);
  return href ? new URL(href).hostname.replace(/^www\./, "") : null;
};

/** The rank to show: Cala's, except unranked rows from known funding databases read "Aggregator". */
export function displayRank(s: Source): SourceRank {
  if (s.rank !== "UNKNOWN") return s.rank;
  const host = hostOf(s.url);
  return host && AGGREGATOR_HOSTS.some((h) => host === h || host.endsWith(`.${h}`)) ? "AGGREGATOR" : "UNKNOWN";
}

/** Who published it, short: the website ("tracxn.com"), else Cala's name for the source. */
export function publisher(s: Source): string {
  const host = hostOf(s.url);
  if (host) return host;
  const name = s.name.replace(/^www\./, "").trim();
  return name.length > 32 ? `${name.slice(0, 31).trimEnd()}…` : name;
}

/**
 * Sorted, with repeats folded: the same publisher on the same date counts once (Cala often cites
 * two pages of one database for one claim). `count` says how many sources were folded together.
 */
export function dedupeSources(sources: Source[]): { source: Source; count: number }[] {
  const out: { source: Source; count: number }[] = [];
  const seen = new Map<string, { source: Source; count: number }>();
  for (const s of sortSources(sources)) {
    const key = `${publisher(s)}|${s.date ?? ""}`;
    const hit = seen.get(key);
    if (hit) hit.count += 1;
    else {
      const entry = { source: s, count: 1 };
      seen.set(key, entry);
      out.push(entry);
    }
  }
  return out;
}

/** Best rank first, then newest first. Stable for equal keys; does not mutate. */
export function sortSources(sources: Source[]): Source[] {
  return [...sources].sort((a, b) => {
    const r = RANK_ORDER.indexOf(displayRank(a)) - RANK_ORDER.indexOf(displayRank(b));
    if (r !== 0) return r;
    return (b.date ?? "").localeCompare(a.date ?? "");
  });
}
