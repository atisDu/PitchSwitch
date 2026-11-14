// Source badge: rank, publisher and date, linked, next to every claim (CLAUDE.md §6, C4).
// No client JS: <details> handles "+N more", so it works in server components too.

import { dedupeSources, displayRank, formatSourceDate, publisher, rankLabel, safeUrl } from "@/lib/sources";
import type { Source, SourceRank } from "@/lib/types";

// One accent, so reliability is shown by weight, not hue: teal tints for first-hand sources,
// an ink outline for press, faint for the rest. The landing page's .pw__src look: mono publisher.
const RANK_STYLE: Record<SourceRank, string> = {
  PRIMARY: "border-moss bg-echo text-foreground",
  FILING: "border-moss bg-surface text-foreground",
  PRESS: "border-foreground/40 bg-white text-foreground",
  AGGREGATOR: "border-foreground/15 bg-white text-muted",
  UNKNOWN: "border-dashed border-foreground/20 bg-white text-muted",
};

// overflow-hidden + a shrinking publisher: on a phone the name truncates, the date stays visible.
// Taller on touch screens, so a thumb hits one source, not its neighbour.
const BASE =
  "inline-flex max-w-full items-center gap-1.5 overflow-hidden rounded-md border px-1.5 py-0.5 font-mono text-xs leading-4 whitespace-nowrap pointer-coarse:min-h-8 pointer-coarse:px-2";

/**
 * One source. `bare` shows the rank alone (the legend on /about); `count` > 1 says that several
 * sources from the same publisher and date were folded into this one.
 */
export function SourceBadge({ source, bare = false, count = 1 }: { source: Source; bare?: boolean; count?: number }) {
  const rank = displayRank(source);
  const date = bare ? null : formatSourceDate(source.date);
  const href = bare ? null : safeUrl(source.url);
  const from = bare ? null : publisher(source);
  const title = [rankLabel(rank), source.name, source.date, source.url].filter(Boolean).join(" · ");
  const body = (
    <>
      <span className="shrink-0 font-sans font-medium text-foreground">{rankLabel(rank)}</span>
      {from && <span className="max-w-[13rem] min-w-0 truncate">{from}</span>}
      {date && <span className="shrink-0">{date}</span>}
      {count > 1 && (
        <span className="shrink-0" aria-hidden="true">
          ×{count}
        </span>
      )}
      {href && (
        <span className="shrink-0" aria-hidden="true">
          ↗
        </span>
      )}
    </>
  );
  const spoken = `${rankLabel(rank)} source${from ? `: ${from}` : ""}${date ? `, ${date}` : ""}${
    count > 1 ? `, ${count} pages` : ""
  }`;

  if (!href) {
    return (
      <span className={`${BASE} ${RANK_STYLE[rank]}`} title={title} aria-label={bare ? undefined : spoken}>
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
      aria-label={`${spoken} (opens in a new tab)`}
      className={`${BASE} ${RANK_STYLE[rank]} hover:border-foreground`}
    >
      {body}
    </a>
  );
}

/**
 * All sources of one claim: the most reliable first, repeats folded, the rest behind "+N".
 * Renders "No source" when the list is empty, so a missing source is visible.
 */
export function SourceBadges({ sources, max = 1 }: { sources: Source[]; max?: number }) {
  if (sources.length === 0) {
    return <span className={`${BASE} ${RANK_STYLE.UNKNOWN} italic`}>No source</span>;
  }
  const entries = dedupeSources(sources);
  const shown = entries.slice(0, max);
  const rest = entries.slice(max);
  return (
    <span className="inline-flex max-w-full flex-wrap items-center gap-1 align-middle">
      {shown.map((e, i) => (
        <SourceBadge key={`${e.source.url ?? e.source.name}-${i}`} source={e.source} count={e.count} />
      ))}
      {rest.length > 0 && (
        <details className="group inline-block max-w-full">
          <summary
            className={`${BASE} ${RANK_STYLE.UNKNOWN} cursor-pointer list-none hover:text-foreground [&::-webkit-details-marker]:hidden`}
            aria-label={`${rest.length} more ${rest.length === 1 ? "source" : "sources"}`}
          >
            <span className="group-open:hidden">+{rest.length}</span>
            <span className="hidden group-open:inline">less</span>
          </summary>
          <span className="mt-1 flex flex-wrap gap-1">
            {rest.map((e, i) => (
              <SourceBadge key={`${e.source.url ?? e.source.name}-${i}`} source={e.source} count={e.count} />
            ))}
          </span>
        </details>
      )}
    </span>
  );
}
