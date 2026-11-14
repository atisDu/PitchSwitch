"use client";

// Founder report (C5, C6): company header and a one-line verdict, competitor chips, the Skip
// list in brief (the core value, kept above the fold of the lists), the Pitch list, then the
// evidence for each Skip. Removing competitors and pressing "Re-rank" calls
// /api/founder/analyze again with the remaining `competitor_ids`.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";
import { CompetitorChips } from "@/components/CompetitorChips";
import { AmountField } from "@/components/FundingFit";
import { PitchCard, SkipCard } from "@/components/InvestorCard";
import { SlowNotice } from "@/components/SlowNotice";
import { SourceBadges } from "@/components/SourceBadge";
import { analyzeFounder } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { displayName, keptCompetitorIds, prettyDates, prettyEnum } from "@/lib/format";
import { conflictText, skipCause } from "@/lib/investor";
import { dedupeSources } from "@/lib/sources";
import { prepPath } from "@/lib/routes";
import type { Company, Conflict, FounderReport, InvestorScore } from "@/lib/types";

// Live reports rank 30-45 investors; the top ones matter. The Skip list is summarised above
// the Pitch list, so showing more here no longer pushes it out of reach.
const PITCH_SHOWN = 5;

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean; detail: string | null }
  | { status: "ready"; report: FounderReport; reranking: boolean; rerankError: string | null };

export function FounderReportView({
  companyId,
  initialTarget = null,
}: {
  companyId: string;
  initialTarget?: number | null; // ?raise= in the URL (C18)
}) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [narrowed, setNarrowed] = useState(false); // ranked against a user-edited list
  const [showAllPitch, setShowAllPitch] = useState(false);
  const [target, setTarget] = useState<number | null>(initialTarget); // the founder's raise (B21)
  const abort = useRef<AbortController | null>(null);

  // Fetches and stores a report. State is set only in the promise callbacks, so the initial
  // load can run from an effect; `run` below flips the loading state first, from handlers.
  const fetchReport = useCallback(
    (competitorIds?: string[], raise?: number | null) => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      return analyzeFounder(
        {
          company_id: companyId,
          ...(competitorIds ? { competitor_ids: competitorIds } : {}),
          ...(raise ? { target_amount_eur: raise } : {}),
        },
        ctrl.signal,
      ).then(
        (report) => {
          if (ctrl.signal.aborted) return;
          setLoad({ status: "ready", report, reranking: false, rerankError: null });
          setRemoved(new Set());
          setNarrowed(Boolean(competitorIds));
          setShowAllPitch(false);
        },
        (err: unknown) => {
          if (ctrl.signal.aborted) return;
          const e = describeError(err);
          setLoad((prev) =>
            prev.status === "ready" && competitorIds
              ? { ...prev, reranking: false, rerankError: e.message }
              : { status: "error", message: e.message, notFound: e.notFound, detail: e.detail },
          );
        },
      );
    },
    [companyId],
  );

  function run(competitorIds?: string[], raise: number | null = target, keepReport = false) {
    setLoad((prev) =>
      prev.status === "ready" && (competitorIds || keepReport)
        ? { ...prev, reranking: true, rerankError: null }
        : { status: "loading" },
    );
    void fetchReport(competitorIds, raise);
  }

  // A new raise re-ranks against the same competitors, and is kept in the URL (?raise=).
  function applyRaise(raise: number | null) {
    setTarget(raise);
    const url = new URL(window.location.href);
    if (raise) url.searchParams.set("raise", String(raise));
    else url.searchParams.delete("raise");
    window.history.replaceState(null, "", url);
    const current =
      load.status === "ready" && narrowed ? load.report.competitors.map((c) => c.company.id) : undefined;
    run(current, raise, true);
  }

  useEffect(() => {
    void fetchReport(undefined, initialTarget);
    return () => abort.current?.abort();
  }, [fetchReport, initialTarget]);

  if (load.status === "loading") return <LoadingReport />;
  if (load.status === "error") {
    return (
      <div className="max-w-xl">
        <h1 className="display text-5xl">
          {load.notFound ? "We couldn't find that company." : "The report didn't load."}
        </h1>
        <p className="mt-6 border-l-2 border-foreground pl-3">{load.message}</p>
        {load.detail && (
          <details className="mt-3 text-sm text-muted">
            <summary className="cursor-pointer">Technical details</summary>
            <p className="mt-2 font-mono text-xs break-all">{load.detail}</p>
          </details>
        )}
        <div className="mt-8 flex gap-3">
          {!load.notFound && (
            <button type="button" className="btn-primary" onClick={() => void run()}>
              Try again
            </button>
          )}
          <Link href="/start" className="btn-ghost h-control-lg">
            Search again
          </Link>
        </div>
      </div>
    );
  }

  const { report, reranking, rerankError } = load;
  const ids = report.competitors.map((c) => c.company.id);
  const kept = keptCompetitorIds(ids, removed);
  const name = displayName(report.company.name);
  const noFitYet = target !== null && !reranking && ![...report.pitch, ...report.skip].some((s) => s.funding_fit);

  return (
    <div>
      <title>{`${name} · Founder report · PitchSwitch`}</title>
      <ChatPanel
        companyId={report.company.id}
        scope={name}
        suggestions={[
          "Who are my top 3 investors to pitch, and why?",
          ...(report.skip[0] ? [`Why should I skip ${displayName(report.skip[0].investor.name)}?`] : []),
          ...(report.pitch[0] ? [`What has ${displayName(report.pitch[0].investor.name)} led recently?`] : []),
        ]}
      />
      <CompanyHeader company={report.company} />
      <Verdict report={report} />

      <section id="competitors" className="window mt-12 scroll-mt-24 p-5 md:p-7" aria-labelledby="competitors-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <p id="competitors-heading" className="label">
              Competitors · {kept.length}
            </p>
            <p className="mt-2 max-w-xl text-sm text-muted">
              Investors who backed these go on the Skip list. Hover or tap a name to see why it
              counts; remove the ones that don&apos;t, then re-rank.
            </p>
          </div>
          <div className="flex items-center gap-4">
            {narrowed && removed.size === 0 && (
              <button
                type="button"
                disabled={reranking}
                onClick={() => void run()}
                className="text-sm underline underline-offset-4 disabled:opacity-40"
              >
                Reset to all competitors
              </button>
            )}
            {removed.size > 0 && (
              <button
                type="button"
                disabled={reranking}
                onClick={() => void run(kept)}
                className="btn-primary"
              >
                {reranking ? "Re-ranking…" : `Re-rank with ${kept.length}`}
              </button>
            )}
          </div>
        </div>
        {reranking && <SlowNotice />}
        {rerankError && (
          <p className="mt-4 border-l-2 border-foreground pl-3 text-sm">
            Re-ranking failed: {rerankError}
          </p>
        )}
        <div className="mt-6">
          {report.competitors.length === 0 ? (
            <p className="text-muted">
              No direct competitors found in Cala, so no investor has a conflict yet.
            </p>
          ) : (
            <CompetitorChips
              competitors={report.competitors}
              removed={removed}
              disabled={reranking}
              onRemove={(id) => setRemoved((s) => new Set(s).add(id))}
              onRestore={(id) =>
                setRemoved((s) => {
                  const next = new Set(s);
                  next.delete(id);
                  return next;
                })
              }
            />
          )}
        </div>
        {report.notes.length > 0 && <CompetitorNotes notes={report.notes} />}
      </section>

      <div className={`transition-opacity ${reranking ? "opacity-40" : ""}`} aria-busy={reranking}>
        {report.skip.length > 0 && <SkipRollCall report={report} />}

        <section className="mt-20" aria-labelledby="pitch-heading">
          <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-8">
            <ListHeading
              id="pitch-heading"
              title="Who to pitch"
              hint={`${count(report.pitch.length, "investor")} with no conflict, ranked by fit: how often they lead and invest in your space, how recently and actively, warm paths, stage fit and a Nordic or Baltic focus. Open a card to see how its score adds up.`}
            />
            <div className="w-full max-w-xs">
              <AmountField side="founder" value={target} onApply={applyRaise} disabled={reranking} />
            </div>
          </div>
          {noFitYet && (
            <p className="mt-4 text-sm text-muted">
              Fit by round size isn&apos;t available on this server yet; it will show on each card once
              it is.
            </p>
          )}
          {report.pitch.length === 0 ? (
            <p className="mt-6 border-t border-line pt-6 text-muted">
              No investors without a conflict found in your space yet.
            </p>
          ) : (
            <>
              <ol className="mt-8">
                {(showAllPitch ? report.pitch : report.pitch.slice(0, PITCH_SHOWN)).map((s, i) => (
                  <li key={s.investor.id}>
                    <PitchCard item={s} rank={i + 1} companyId={report.company.id} companyName={report.company.name} />
                  </li>
                ))}
              </ol>
              {report.pitch.length > PITCH_SHOWN && (
                <button
                  type="button"
                  onClick={() => setShowAllPitch((v) => !v)}
                  className="btn-ghost mt-2 h-10"
                >
                  {showAllPitch ? `Show top ${PITCH_SHOWN}` : `Show all ${report.pitch.length}`}
                </button>
              )}
            </>
          )}
        </section>

        {report.skip.length > 0 && (
          <section className="mt-20" aria-labelledby="skip-heading">
            <ListHeading
              id="skip-heading"
              title="Why to skip each one"
              hint="They backed a direct competitor, or one of their people sits on its board. Each conflict links to the sources it rests on; flip to see it from the fund's side."
            />
            <ul className="mt-8">
              {report.skip.map((s) => (
                <li key={s.investor.id}>
                  <SkipCard item={s} companyId={report.company.id} companyName={report.company.name} />
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <section className="lit-ground mt-20 rounded-[20px] px-6 py-12 md:px-12 md:py-16 print:hidden" aria-label="Next step">
        <p className="display text-4xl md:text-5xl">Meeting investors at Slush?</p>
        <p className="mt-3 max-w-xl text-foreground/80">
          Paste the funds from your calendar and get a one-page brief on each.
        </p>
        <Link href={prepPath(report.company)} className="btn-primary mt-6">
          Prep a brief for each meeting
        </Link>
      </section>
    </div>
  );
}

const count = (n: number, one: string) => `${n} ${n === 1 ? one : `${one}s`}`;

/** The report in one sentence, before any detail: how many to skip, how many to pitch. */
function Verdict({ report }: { report: FounderReport }) {
  const comps = count(report.competitors.length, "direct competitor");
  if (report.skip.length === 0) {
    return (
      <p className="mt-10 max-w-3xl text-2xl leading-snug md:text-3xl">
        No conflicts: none of the investors in your space backed your {comps}.{" "}
        <a href="#pitch-heading" className="underline decoration-accent decoration-2 underline-offset-4">
          {report.pitch.length} to pitch
        </a>
        .
      </p>
    );
  }
  return (
    <p className="mt-10 max-w-3xl text-2xl leading-snug md:text-3xl">
      <a href="#skip-summary" className="font-medium underline decoration-accent decoration-4 underline-offset-4">
        {count(report.skip.length, "investor")} to skip
      </a>
      , because they {skipCause(report.skip)}.{" "}
      <a href="#pitch-heading" className="underline decoration-line decoration-2 underline-offset-4 hover:decoration-foreground">
        {report.pitch.length} to pitch
      </a>
      , ranked by fit.
    </p>
  );
}

function shortConflict(c: Conflict, s: InvestorScore, chips: Set<string>): string {
  if (c.kind === "SANCTION") {
    return c.competitor.id === s.investor.id ? "sanctions record" : `LP ${displayName(c.competitor.name)}: sanctions record`;
  }
  if (c.kind === "BOARD") return `board seat at ${displayName(c.competitor.name)}`;
  // B22: the X-ray finds direct rivals in a portfolio that are not among the chips above.
  const hidden = !chips.has(c.competitor.id) ? " (a rival found in its portfolio)" : "";
  return `backed ${displayName(c.competitor.name)}${hidden}`;
}

/** The line under "Don't pitch these N.": the rival's-backer warning, and a sanctions note when one occurs. */
function skipCopy(skip: InvestorScore[]): string {
  const sanctioned = skip.some((s) => s.conflicts.some((c) => c.kind === "SANCTION"));
  const rivals = skip.some((s) => s.conflicts.some((c) => c.kind !== "SANCTION"));
  const parts: string[] = [];
  if (rivals) parts.push("Pitching a fund that backed a direct competitor means handing your deck to a rival's backer.");
  if (sanctioned) parts.push("A sanctions record in Cala, on the fund or one of its LPs, rules a fund out on its own.");
  return parts.join(" ");
}

/** The Skip list in one line per fund, above the Pitch list: the core value, within reach. */
function SkipRollCall({ report }: { report: FounderReport }) {
  const chips = new Set(report.competitors.map((c) => c.company.id));
  return (
    <section
      className="mt-12 rounded-[20px] bg-press px-6 py-10 text-background md:px-10 md:py-12"
      aria-labelledby="skip-summary"
    >
      <h2 id="skip-summary" className="display scroll-mt-24 text-4xl md:text-5xl">
        Don&apos;t pitch these {report.skip.length}.
      </h2>
      <p className="mt-3 max-w-2xl text-sage">
        {skipCopy(report.skip)}
      </p>
      <ul className="mt-8 divide-y divide-slate border-y border-slate">
        {report.skip.map((s) => (
          <li key={s.investor.id} className="grid items-baseline gap-x-6 gap-y-1 py-3 sm:grid-cols-[minmax(0,20rem)_1fr]">
            <a href={`#skip-${s.investor.id}`} className="text-lg font-medium underline-offset-4 hover:underline pointer-coarse:inline-block pointer-coarse:py-2.5">
              {displayName(s.investor.name)}
            </a>
            <span className="text-sage">{s.conflicts.map((c) => shortConflict(c, s, chips)).join(" · ")}</span>
          </li>
        ))}
      </ul>
      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
        <CopySkipList report={report} />
        <a href="#skip-heading" className="text-sm text-sage underline underline-offset-4 hover:text-background">
          See the evidence for each ↓
        </a>
      </div>
    </section>
  );
}

/** Plain text for a CRM or meeting notes, with up to two source links per conflict. */
function skipListText(report: FounderReport): string {
  const lines = report.skip.map((s) => {
    const why = s.conflicts.map((c) => conflictText(c, s.investor.id)).join("; ");
    const urls = dedupeSources(s.conflicts.flatMap((c) => c.sources))
      .map((e) => e.source.url)
      .filter(Boolean)
      .slice(0, 2);
    return `- ${displayName(s.investor.name)}: ${why}${urls.length ? ` (sources: ${urls.join(", ")})` : ""}`;
  });
  return [`Investors to skip for ${displayName(report.company.name)} (PitchSwitch, data from Cala):`, ...lines].join("\n");
}

function CopySkipList({ report }: { report: FounderReport }) {
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  return (
    <button
      type="button"
      className="btn-primary"
      onClick={() => {
        navigator.clipboard.writeText(skipListText(report)).then(
          () => setCopied("done"),
          () => setCopied("failed"),
        );
        window.setTimeout(() => setCopied("idle"), 2500);
      }}
    >
      <span aria-live="polite">
        {copied === "done" ? "Copied" : copied === "failed" ? "Couldn't copy" : "Copy the Skip list"}
      </span>
    </button>
  );
}

/** B24's sourced lines on the competitors: grants they won, and which are at Slush 2026. */
function CompetitorNotes({ notes }: { notes: FounderReport["notes"] }) {
  return (
    <div className="mt-6 border-t border-line pt-5">
      <p className="label">Also about your competitors</p>
      <ul className="mt-2 space-y-2">
        {notes.map((n, i) => (
          <li key={`${n.text}-${i}`} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span>{prettyDates(n.text)}</span>
            <SourceBadges sources={n.sources} max={2} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function ListHeading({ id, title, hint }: { id: string; title: string; hint: string }) {
  return (
    <div className="max-w-2xl">
      <h2 id={id} className="display scroll-mt-24 text-4xl md:text-5xl">
        {title}
      </h2>
      <p className="mt-4 text-muted">{hint}</p>
    </div>
  );
}

function CompanyHeader({ company }: { company: Company }) {
  const facts = [
    company.stage,
    company.country,
    ...company.industries.map(prettyEnum),
    company.total_funding_text && `${company.total_funding_text} raised`,
  ].filter(Boolean);
  return (
    <header>
      <p className="inline-flex h-8 items-center rounded-full border border-line bg-white px-3 text-[13px] text-muted">
        Founder report
      </p>
      <h1 className="display mt-5 text-5xl break-words sm:text-6xl md:text-7xl">{displayName(company.name)}</h1>
      {facts.length > 0 && (
        <p className="label mt-6 flex flex-wrap gap-x-4 gap-y-1 text-muted">
          {facts.map((f) => (
            <span key={f as string}>{f}</span>
          ))}
        </p>
      )}
      {company.description && (
        <p className="mt-4 max-w-2xl text-lg leading-snug">{company.description}</p>
      )}
      <div className="mt-4">
        <SourceBadges sources={company.sources} />
      </div>
    </header>
  );
}

function LoadingReport() {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="h-20 w-2/3 max-w-xl animate-pulse rounded-[14px] bg-surface" />
      <p className="mt-8 max-w-xl text-muted">
        Finding your competitors in Cala, then the rounds they raised and the investors behind
        them.
      </p>
      <SlowNotice />
      <div className="mt-12 flex gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-9 w-28 animate-pulse rounded-lg bg-surface" />
        ))}
      </div>
    </div>
  );
}
