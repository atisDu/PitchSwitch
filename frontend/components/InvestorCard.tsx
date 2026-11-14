// Investor cards for the founder report (C6). Pitch cards lead with fit; Skip
// cards lead with the conflict, because that is the reason they are there.

import Link from "next/link";

import { FundingFitLine } from "@/components/FundingFit";
import { SourceBadges } from "@/components/SourceBadge";
import { activitySummary, conflictText, leadSummary } from "@/lib/investor";
import { briefPath, checkPath } from "@/lib/routes";
import { splitReasons, type ScoreBreakdown } from "@/lib/score";
import type { InvestorScore, Reason, Source } from "@/lib/types";

const VISIBLE_REASONS = 3;

export function PitchCard({
  item,
  rank,
  companyId,
  companyName,
}: {
  item: InvestorScore;
  rank: number;
  companyId: string;
  companyName: string;
}) {
  return (
    <article className="grid grid-cols-[2.5rem_1fr] gap-x-4 border-t border-line py-6 md:grid-cols-[4rem_1fr_7rem]">
      <p className="display text-3xl text-muted md:text-4xl" aria-label={`Rank ${rank}`}>
        {String(rank).padStart(2, "0")}
      </p>
      <div className="min-w-0">
        <Name item={item} />
        <Signals item={item} />
        {item.funding_fit && (
          <div className="mt-3">
            <FundingFitLine fit={item.funding_fit} side="founder" />
          </div>
        )}
        <Breakdown item={item} open={rank === 1} />
        <Reasons reasons={splitReasons(item.reasons).rest} />
        <WarmPaths paths={item.warm_paths} />
        <p className="mt-4 text-sm">
          <Link
            href={briefPath(item.investor.id, companyId, { investor: item.investor.name, company: companyName })}
            className="underline underline-offset-4"
          >
            Read the brief
          </Link>
        </p>
      </div>
      <Score value={item.score} />
    </article>
  );
}

export function SkipCard({
  item,
  companyId,
  companyName,
}: {
  item: InvestorScore;
  companyId: string;
  companyName: string;
}) {
  return (
    <article className="border-t border-line py-6">
      <div className="border-l-4 border-press pl-4 md:pl-6">
        <Name item={item} />
        <ul className="mt-3 space-y-2">
          {item.conflicts.map((c, i) => (
            <li key={`${c.competitor.id}-${c.kind}-${i}`}>
              <p className="text-lg leading-snug font-medium">
                <span className="label mr-2 inline-block rounded-[5px] bg-press px-1.5 py-1 align-middle text-background">
                  {c.kind === "BOARD" ? "Board conflict" : "Conflict"}
                </span>
                {conflictText(c)}
              </p>
              <div className="mt-1.5">
                <SourceBadges sources={c.sources} max={2} />
              </div>
            </li>
          ))}
        </ul>
        {item.funding_fit && (
          <div className="mt-3">
            <FundingFitLine fit={item.funding_fit} side="founder" />
          </div>
        )}
        <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <Link href={checkPath(item.investor.id, companyId)} className="underline underline-offset-4">
            Flip: see this from {item.investor.name}&apos;s side
          </Link>
          <Link
            href={briefPath(item.investor.id, companyId, { investor: item.investor.name, company: companyName })}
            className="underline underline-offset-4"
          >
            Read the brief
          </Link>
        </p>
        <details className="group mt-4">
          <summary className="label cursor-pointer list-none text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
            <span className="group-open:hidden">
              + Other signals · fit despite the conflict {Math.round(item.score)}/100
            </span>
            <span className="hidden group-open:inline">− Other signals</span>
          </summary>
          <Signals item={item} />
          <Breakdown item={item} open skip />
          <Reasons reasons={splitReasons(item.reasons).rest} all />
          <WarmPaths paths={item.warm_paths} />
        </details>
      </div>
    </article>
  );
}

function Name({ item }: { item: InvestorScore }) {
  return (
    <h3 className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <span className="text-xl font-medium tracking-tight">{item.investor.name}</span>
      <span className="label text-muted">{item.investor.type === "Person" ? "Angel" : item.investor.type}</span>
    </h3>
  );
}

function Signals({ item }: { item: InvestorScore }) {
  return (
    <p className="mt-2 text-sm text-muted">
      {leadSummary(item)}
      <span aria-hidden="true"> · </span>
      {activitySummary(item)}
    </p>
  );
}

function Score({ value }: { value: number }) {
  const v = Math.round(value);
  return (
    <div className="col-start-2 mt-4 md:col-start-auto md:mt-0 md:text-right">
      <p className="display text-4xl text-muted md:text-5xl">{v}</p>
      <p className="label mt-1 text-muted">Fit / 100</p>
      <div className="mt-2 h-1 w-24 bg-surface md:ml-auto" aria-hidden="true">
        <div className="h-1 bg-accent" style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
      </div>
    </div>
  );
}

/**
 * How the score adds up (C17): B's first reason as one bar per signal. Each bar's track is as
 * long as that signal's weight, so the 25-point signals look bigger than the 10-point ones.
 */
function Breakdown({ item, open = false, skip = false }: { item: InvestorScore; open?: boolean; skip?: boolean }) {
  const { breakdown, source } = splitReasons(item.reasons);
  if (!breakdown) return null;
  const title = skip
    ? `How the ${fmt(breakdown.total)} (fit despite the conflict) adds up`
    : `How the ${fmt(breakdown.total)} adds up`;
  return (
    <details className="group/b mt-4" open={open}>
      <summary className="label cursor-pointer list-none text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
        <span className="group-open/b:hidden">+ {title}</span>
        <span className="hidden group-open/b:inline">− {title}</span>
      </summary>
      <BreakdownRows breakdown={breakdown} sources={source?.sources ?? []} />
    </details>
  );
}

function BreakdownRows({ breakdown, sources }: { breakdown: ScoreBreakdown; sources: Source[] }) {
  const widest = Math.max(...breakdown.parts.map((p) => p.max), 1);
  return (
    <div className="mt-3">
      <table className="w-full max-w-2xl text-sm">
        <caption className="sr-only">Score breakdown, {fmt(breakdown.total)} out of {breakdown.outOf}</caption>
        <tbody>
          {breakdown.parts.map((p) => (
            <tr key={p.name} className="align-top">
              <th scope="row" className="w-36 py-1 pr-3 text-left font-normal first-letter:uppercase">
                {p.name}
              </th>
              <td className="w-40 py-1 pr-3">
                <div
                  className="mt-1.5 h-1.5 bg-surface"
                  style={{ width: `${(p.max / widest) * 100}%` }}
                  role="img"
                  aria-label={`${fmt(p.got)} of ${fmt(p.max)} points`}
                >
                  <div className="h-1.5 bg-accent" style={{ width: `${p.max ? Math.min(100, (p.got / p.max) * 100) : 0}%` }} />
                </div>
              </td>
              <td className="w-14 py-1 pr-3 text-right tabular-nums">
                {fmt(p.got)}/{fmt(p.max)}
              </td>
              <td className="py-1 text-muted">{p.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sources.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
          Rounds counted <SourceBadges sources={sources} />
        </div>
      )}
    </div>
  );
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

function Reasons({ reasons, all = false }: { reasons: Reason[]; all?: boolean }) {
  if (reasons.length === 0) return null;
  const shown = all ? reasons : reasons.slice(0, VISIBLE_REASONS);
  const rest = all ? [] : reasons.slice(VISIBLE_REASONS);
  return (
    <div className="mt-4">
      <ReasonList reasons={shown} />
      {rest.length > 0 && (
        <details className="group mt-2">
          <summary className="label cursor-pointer list-none text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
            <span className="group-open:hidden">+ {rest.length} more</span>
            <span className="hidden group-open:inline">− Fewer</span>
          </summary>
          <ReasonList reasons={rest} />
        </details>
      )}
    </div>
  );
}

function ReasonList({ reasons }: { reasons: Reason[] }) {
  return (
    <ul className="space-y-1.5">
      {reasons.map((r, i) => (
        <li key={`${r.text}-${i}`} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span>{r.text}</span>
          <SourceBadges sources={r.sources} />
        </li>
      ))}
    </ul>
  );
}

function WarmPaths({ paths }: { paths: Reason[] }) {
  if (paths.length === 0) return null;
  return (
    <div className="mt-4">
      <p className="label">Warm path</p>
      <ul className="mt-1.5 space-y-1.5">
        {paths.map((p, i) => (
          <li key={`${p.text}-${i}`} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className="border-b-2 border-accent">{p.text}</span>
            {/* co_investors() has no sources yet (notes/B.md): say where it comes from instead of "No source". */}
            {p.sources.length > 0 ? (
              <SourceBadges sources={p.sources} />
            ) : (
              <span className="text-xs text-muted">from co-investment data</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
