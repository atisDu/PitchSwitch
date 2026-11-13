// Source badge: rank + date + link, shown next to every claim (CLAUDE.md §6, C4).
// No client JS: <details> handles "+N more", so it works in server components too.

import { formatSourceDate, rankLabel, safeUrl, sortSources } from "@/lib/sources";
import type { Source, SourceRank } from "@/lib/types";

// DESIGN.md allows one accent, so reliability is shown by weight, not hue:
// green tints for first-hand sources, ink outline for press, faint for the rest.
const RANK_STYLE: Record<SourceRank, string> = {
  PRIMARY: "border-moss bg-echo text-foreground",
  FILING: "border-moss bg-surface text-foreground",
  PRESS: "border-foreground/40 bg-background text-foreground",
  AGGREGATOR: "border-line bg-background text-muted",
  UNKNOWN: "border-dashed border-line bg-background text-muted",
};

const BASE =
  "inline-flex max-w-full items-center gap-1.5 rounded-[5px] border px-1.5 py-0.5 text-xs leading-4 whitespace-nowrap";

export function SourceBadge({ source }: { source: Source }) {
  const date = formatSourceDate(source.date);
  const href = safeUrl(source.url);
  const title = [source.name, source.date, source.url].filter(Boolean).join(" · ");
  const body = (
    <>
      <span className="label">{rankLabel(source.rank)}</span>
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
      className={`${BASE} ${RANK_STYLE[source.rank]} hover:border-foreground`}
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
