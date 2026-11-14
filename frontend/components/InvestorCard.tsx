// Investor cards for the founder report (C6). Pitch cards lead with fit; Skip
// cards lead with the conflict, because that is the reason they are there.

import Link from "next/link";

import { FundingFitLine } from "@/components/FundingFit";
import { SourceBadges } from "@/components/SourceBadge";
import { displayName, investorKind, possessive, prettyDates } from "@/lib/format";
import { activitySummary, conflictText, leadSummary } from "@/lib/investor";
import { briefPath, checkPath } from "@/lib/routes";
import { cardReasons, hiddenFor, type Partner } from "@/lib/reasons";
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
  const extra = cardReasons(splitReasons(item.reasons).rest);
  return (
    <article
      id={`pitch-${item.investor.id}`}
      className="window mb-3 grid scroll-mt-24 grid-cols-[2.5rem_1fr] gap-x-4 p-5 transition-transform duration-200 hover:-translate-y-0.5 md:grid-cols-[4rem_1fr_7rem] md:p-7"
    >
      <p className="display text-3xl text-muted md:text-4xl" aria-label={`Rank ${rank}`}>
        {String(rank).padStart(2, "0")}
      </p>
      <div className="min-w-0">
        <Name item={item} tag={extra.freshFund ? "Fresh fund" : null} />
        <Signals item={item} />
        {extra.freshFund && <FreshFund reason={extra.freshFund} />}
        {item.funding_fit && (
          <div className="mt-3">
            <FundingFitLine fit={item.funding_fit} side="founder" />
          </div>
        )}
        <Breakdown item={item} open={rank === 1} />
        <Reasons reasons={extra.rest} />
        {extra.partner && <PartnerLine partner={extra.partner} />}
        <WarmPaths paths={item.warm_paths} />
        <p className="mt-4 text-sm">
          <Link
            href={briefPath(item.investor.id, companyId, { investor: item.investor.name, company: companyName })}
            className="underline underline-offset-4 pointer-coarse:inline-block pointer-coarse:py-2.5"
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
  const extra = cardReasons(splitReasons(item.reasons).rest);
  return (
    <article id={`skip-${item.investor.id}`} className="window mb-3 scroll-mt-24 p-5 target:outline-2 target:outline-accent md:p-7">
      <div className="border-l-4 border-foreground pl-4 md:pl-6">
        <Name item={item} />
        <ul className="mt-3 space-y-2">
          {item.conflicts.map((c, i) => {
            const hidden = c.kind === "PORTFOLIO" ? hiddenFor(extra.hidden, c.competitor.name) : null;
            return (
              <li key={`${c.competitor.id}-${c.kind}-${i}`}>
                <p className="text-lg leading-snug font-medium">
                  <span className="label mr-2 inline-block rounded-md bg-foreground px-2 py-1 align-middle text-white">
                    {c.kind === "BOARD" ? "Board conflict" : c.kind === "SANCTION" ? "Sanctions" : hidden ? "Hidden conflict" : "Conflict"}
                  </span>
                  {hidden
                    ? `Backs ${displayName(c.competitor.name)}, a direct rival not on your competitor list`
                    : conflictText(c, item.investor.id)}
                </p>
                {hidden?.why && <p className="mt-1 max-w-2xl text-sm text-muted">{hidden.why}</p>}
                <div className="mt-1.5">
                  <SourceBadges sources={c.sources} max={2} />
                </div>
              </li>
            );
          })}
        </ul>
        {item.funding_fit && (
          <div className="mt-3">
            <FundingFitLine fit={item.funding_fit} side="founder" />
          </div>
        )}
        <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <Link href={checkPath(item.investor.id, companyId)} className="underline underline-offset-4 pointer-coarse:inline-block pointer-coarse:py-2.5">
            See it from {possessive(displayName(item.investor.name))} side
          </Link>
          <Link
            href={briefPath(item.investor.id, companyId, { investor: item.investor.name, company: companyName })}
            className="underline underline-offset-4 pointer-coarse:inline-block pointer-coarse:py-2.5"
          >
            Read the brief
          </Link>
        </p>
        <details className="group mt-4">
          <summary className="label pointer-coarse:py-2.5 cursor-pointer list-none text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
            <span className="group-open:hidden">
              + Other signals · fit despite the conflict {Math.round(item.score)}/100
            </span>
            <span className="hidden group-open:inline">− Other signals</span>
          </summary>
          <Signals item={item} />
          <Breakdown item={item} open skip />
          <Reasons reasons={extra.rest} all />
          {extra.partner && <PartnerLine partner={extra.partner} />}
          <WarmPaths paths={item.warm_paths} />
        </details>
      </div>
    </article>
  );
}

function Name({ item, tag = null }: { item: InvestorScore; tag?: string | null }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <h3 className="text-xl font-medium tracking-tight">{displayName(item.investor.name)}</h3>
      <span className="label text-muted">{investorKind(item.investor.type)}</span>
      {tag && <span className="label self-center rounded-md bg-accent px-2 py-0.5 text-white">{tag}</span>}
    </div>
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
      <p className="display text-4xl text-accent md:text-5xl">{v}</p>
      <p className="label mt-1 text-muted">Fit / 100</p>
      <div className="mt-2 h-1.5 w-24 overflow-hidden rounded-full bg-surface md:ml-auto" aria-hidden="true">
        <div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
      </div>
    </div>
  );
}

/** How the score adds up (C17), folded in the report's cards; the first Pitch card opens it. */
function Breakdown({ item, open = false, skip = false }: { item: InvestorScore; open?: boolean; skip?: boolean }) {
  const { breakdown, source } = splitReasons(item.reasons);
  if (!breakdown) return null;
  return (
    <ScoreBox
      breakdown={breakdown}
      sources={source?.sources ?? []}
      title={skip ? "Fit despite the conflict" : "How the score adds up"}
      open={open}
    />
  );
}

/**
 * The score breakdown in its own tinted box: B's first reason as one row per signal, with the
 * points ("11.3 / 15": the "/ 15" is the signal's weight), a bar and what they were given for. `open` undefined: always
 * open (the brief); true or false: a box that folds, open or closed at first (the report's cards).
 */
export function ScoreBox({
  breakdown,
  sources,
  title,
  note,
  open,
}: {
  breakdown: ScoreBreakdown;
  sources: Source[];
  title: string;
  note?: string; // under the title, e.g. which list the investor is on
  open?: boolean;
}) {
  const head = (
    <span className="flex items-baseline justify-between gap-4">
      <span className="min-w-0">
        <span className="block font-medium">{title}</span>
        {note && <span className="mt-0.5 block text-sm text-muted">{note}</span>}
      </span>
      <span className="shrink-0 tabular-nums">
        <span className="text-2xl font-medium text-accent">{Math.round(breakdown.total)}</span>
        <span className="text-sm text-muted"> / {breakdown.outOf}</span>
      </span>
    </span>
  );
  const body = (
    <>
      <ul className="mt-4 grid gap-x-8 gap-y-4 border-t border-line pt-4 sm:grid-cols-2">
        {breakdown.parts.map((p) => (
          <li key={p.name} className="min-w-0">
            <p className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium first-letter:uppercase">{partName(p.name)}</span>
              <span className="shrink-0 tabular-nums">
                {fmt(p.got)}
                <span className="text-muted"> / {fmt(p.max)}</span>
              </span>
            </p>
            <div className="mt-1.5 h-2 rounded-full bg-white" aria-hidden="true">
              <div
                className="h-2 rounded-full bg-accent"
                style={{ width: `${p.max ? Math.min(100, (p.got / p.max) * 100) : 0}%` }}
              />
            </div>
            {p.detail && <p className="mt-1 text-sm text-muted">{partDetail(p.name, p.detail)}</p>}
          </li>
        ))}
      </ul>
      {sources.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          Rounds counted <SourceBadges sources={sources} />
        </div>
      )}
    </>
  );
  const box = "mt-4 rounded-xl bg-surface p-4 md:p-5";
  if (open === undefined) {
    return (
      <section className={box} aria-label={`${title}: ${Math.round(breakdown.total)} of ${breakdown.outOf}`}>
        {head}
        {body}
      </section>
    );
  }
  return (
    <details className={`group/b ${box}`} open={open}>
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        {head}
        <span className="mt-2 block text-sm text-accent underline underline-offset-4">
          <span className="group-open/b:hidden">Show the breakdown</span>
          <span className="hidden group-open/b:inline">Hide the breakdown</span>
        </span>
      </summary>
      {body}
    </details>
  );
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

// B's signal names, in the words the rest of the app (and /about) uses.
const PART_NAMES: Record<string, string> = { "companies here": "Companies in your space" };
const partName = (name: string) => PART_NAMES[name.toLowerCase()] ?? name;
const plural = (n: string, one: string, many: string) => `${n} ${n === "1" ? one : many}`;
// B's terse details ("2 led", "0") as phrases; anything else passes through.
const partDetail = (name: string, detail: string) => {
  const d = prettyDates(detail)
    .replace(/(\d+(?:\.\d+)?) weighted by closeness/, "worth $1 after weighting by closeness")
    .replace(/^(\d+) in 12 mo$/, (_, n) => plural(n, "deal in the last 12 months", "deals in the last 12 months"))
    .replace(/^(\d+) led\b/, (_, n) => plural(n, "round led", "rounds led"));
  if (name.toLowerCase() === "warm paths") {
    return d.replace(/^0$/, "None through your current investors").replace(/^(\d+)\b/, (_, n) =>
      plural(n, "path through your current investors", "paths through your current investors"),
    );
  }
  return d;
};

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
          <span>{prettyDates(r.text)}</span>
          {/* The sanctions screen's "nothing found" line has no record to cite. */}
          {!(r.text.startsWith("screened: ") && r.sources.length === 0) && <SourceBadges sources={r.sources} />}
        </li>
      ))}
    </ul>
  );
}

/** B23: a fund that just closed a vehicle for the startup's sector, with its sourced claim. */
function FreshFund({ reason }: { reason: Reason }) {
  return (
    <p className="mt-3 flex max-w-3xl flex-wrap items-center gap-x-2 gap-y-1 border-l-2 border-accent pl-3 text-sm">
      <span>{prettyDates(reason.text)}</span>
      <SourceBadges sources={reason.sources} max={1} />
    </p>
  );
}

/** B23: the partner to ask for, named from sourced claims (checked against rivals' boards by B). */
function PartnerLine({ partner }: { partner: Partner }) {
  return (
    <div className="mt-4">
      <p className="label">Ask for</p>
      <p className="mt-1.5 text-sm">
        <span className="font-medium">{partner.name}</span>
        <span className="text-muted"> · {partner.claim}</span>
      </p>
      <div className="mt-1">
        <SourceBadges sources={partner.sources} max={2} />
      </div>
    </div>
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
