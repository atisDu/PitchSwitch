// Source badge: rank + date + link, shown next to every claim (CLAUDE.md §6, C4).
// No client JS: <details> handles "+N more", so it works in server components too.

import { formatSourceDate, rankLabel, safeUrl, sortSources } from "@/lib/sources";
import type { Source, SourceRank } from "@/lib/types";

const RANK_STYLE: Record<SourceRank, string> = {
  PRIMARY:
    "border-emerald-600/30 bg-emerald-50 text-emerald-800 dark:border-emerald-400/30 dark:bg-emerald-950 dark:text-emerald-200",
  FILING:
    "border-teal-600/30 bg-teal-50 text-teal-800 dark:border-teal-400/30 dark:bg-teal-950 dark:text-teal-200",
  PRESS:
    "border-sky-600/30 bg-sky-50 text-sky-800 dark:border-sky-400/30 dark:bg-sky-950 dark:text-sky-200",
  AGGREGATOR:
    "border-amber-600/30 bg-amber-50 text-amber-800 dark:border-amber-400/30 dark:bg-amber-950 dark:text-amber-200",
  UNKNOWN: "border-line bg-surface text-muted",
};

const BASE =
  "inline-flex max-w-full items-center gap-1 rounded border px-1.5 py-0.5 text-xs leading-4 whitespace-nowrap";

export function SourceBadge({ source }: { source: Source }) {
  const date = formatSourceDate(source.date);
  const href = safeUrl(source.url);
  const title = [source.name, source.date, source.url].filter(Boolean).join(" · ");
  const body = (
    <>
      <span className="font-medium">{rankLabel(source.rank)}</span>
      {date && <span className="opacity-75">{date}</span>}
      {href && <span aria-hidden="true">↗</span>}
    </>
  );

  if (!href) {
    return (
      <span className={`${BASE} ${RANK_STYLE[source.rank]}`} title={title}>
        {body}
      </span>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={title}
      aria-label={`${rankLabel(source.rank)} source: ${source.name}${date ? `, ${date}` : ""} (opens in a new tab)`}
      className={`${BASE} ${RANK_STYLE[source.rank]} hover:underline focus-visible:outline-2 focus-visible:outline-offset-1`}
    >
      {body}
    </a>
  );
}

/**
 * All sources of one claim: the most reliable first, the rest behind "+N".
 * Renders "No source" when the list is empty, so a missing source is visible.
 */
export function SourceBadges({ sources, max = 1 }: { sources: Source[]; max?: number }) {
  if (sources.length === 0) {
    return <span className={`${BASE} ${RANK_STYLE.UNKNOWN} italic`}>No source</span>;
  }
  const sorted = sortSources(sources);
  const shown = sorted.slice(0, max);
  const rest = sorted.slice(max);
  return (
    <span className="inline-flex flex-wrap items-center gap-1 align-middle">
      {shown.map((s, i) => (
        <SourceBadge key={`${s.url ?? s.name}-${i}`} source={s} />
      ))}
      {rest.length > 0 && (
        <details className="group inline-block">
          <summary
            className={`${BASE} ${RANK_STYLE.UNKNOWN} cursor-pointer list-none hover:text-foreground [&::-webkit-details-marker]:hidden`}
          >
            <span className="group-open:hidden">+{rest.length}</span>
            <span className="hidden group-open:inline">less</span>
          </summary>
          <span className="mt-1 flex flex-wrap gap-1">
            {rest.map((s, i) => (
              <SourceBadge key={`${s.url ?? s.name}-${i}`} source={s} />
            ))}
          </span>
        </details>
      )}
    </span>
  );
}
