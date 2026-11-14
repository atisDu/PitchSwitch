"use client";

// Founder report (C5, C6): company header, competitor chips, then the Pitch and
// Skip lists. Removing competitors and pressing "Re-rank" calls
// /api/founder/analyze again with the remaining `competitor_ids`.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";
import { CompetitorChips } from "@/components/CompetitorChips";
import { PitchCard, SkipCard } from "@/components/InvestorCard";
import { SlowNotice } from "@/components/SlowNotice";
import { SourceBadges } from "@/components/SourceBadge";
import { analyzeFounder } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { keptCompetitorIds, prettyEnum } from "@/lib/format";
import { prepPath } from "@/lib/routes";
import type { Company, FounderReport } from "@/lib/types";

// Live reports rank 30-45 investors; the top ones matter, and the Skip list below
// (the conflict) must stay within reach: each card is ~235 px tall.
const PITCH_SHOWN = 5;

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean; detail: string | null }
  | { status: "ready"; report: FounderReport; reranking: boolean; rerankError: string | null };

export function FounderReportView({ companyId }: { companyId: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [narrowed, setNarrowed] = useState(false); // ranked against a user-edited list
  const [showAllPitch, setShowAllPitch] = useState(false);
  const abort = useRef<AbortController | null>(null);

  // Fetches and stores a report. State is set only in the promise callbacks, so the initial
  // load can run from an effect; `run` below flips the loading state first, from handlers.
  const fetchReport = useCallback(
    (competitorIds?: string[]) => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      return analyzeFounder(
        { company_id: companyId, ...(competitorIds ? { competitor_ids: competitorIds } : {}) },
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

  function run(competitorIds?: string[]) {
    setLoad((prev) =>
      prev.status === "ready" && competitorIds
        ? { ...prev, reranking: true, rerankError: null }
        : { status: "loading" },
    );
    void fetchReport(competitorIds);
  }

  useEffect(() => {
    void fetchReport();
    return () => abort.current?.abort();
  }, [fetchReport]);

  if (load.status === "loading") return <LoadingReport />;
  if (load.status === "error") {
    return (
      <div className="max-w-xl">
        <p className="label text-muted">Founder report</p>
        <h1 className="display mt-4 text-5xl">
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
          <Link href="/" className="btn-ghost h-[47px]">
            Search again
          </Link>
        </div>
      </div>
    );
  }

  const { report, reranking, rerankError } = load;
  const ids = report.competitors.map((c) => c.company.id);
  const kept = keptCompetitorIds(ids, removed);

  return (
    <div>
      <title>{`${report.company.name} · Founder report · PitchSwitch`}</title>
      <ChatPanel
        companyId={report.company.id}
        scope={report.company.name}
        suggestions={[
          "Who are my top 3 investors to pitch, and why?",
          ...(report.skip[0] ? [`Why should I skip ${report.skip[0].investor.name}?`] : []),
          ...(report.pitch[0] ? [`What has ${report.pitch[0].investor.name} led recently?`] : []),
        ]}
      />
      <CompanyHeader company={report.company} />

      <section className="mt-16 border-t border-line pt-8">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <p className="label">Competitors · {kept.length}</p>
            <p className="mt-2 max-w-xl text-sm text-muted">
              Investors who backed these go on the Skip list. Hover a name to see why it counts;
              remove the ones that don&apos;t, then re-rank.
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
      </section>

      <div className={`transition-opacity ${reranking ? "opacity-40" : ""}`} aria-busy={reranking}>
        <section className="mt-20" aria-labelledby="pitch-heading">
          <ListHeading
            id="pitch-heading"
            label="Pitch"
            count={report.pitch.length}
            title="Who to pitch"
            hint="Ranked by fit: how often they lead in your space, how recently, and warm paths to them. None of them backed your competitors."
          />
          {report.skip.length > 0 && (
            <a href="#skip-heading" className="mt-3 inline-block text-sm underline underline-offset-4">
              Jump to the {report.skip.length} to skip ↓
            </a>
          )}
          {report.pitch.length === 0 ? (
            <p className="mt-6 border-t border-line pt-6 text-muted">
              No investors without a conflict found in your space yet.
            </p>
          ) : (
            <>
              <ol className="mt-6">
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

        <section className="mt-20" aria-labelledby="skip-heading">
          <ListHeading
            id="skip-heading"
            label="Skip"
            count={report.skip.length}
            title="Who to skip"
            hint="They backed a direct competitor, or one of their people sits on its board. Pitching them means handing your deck to a rival's backer."
          />
          {report.skip.length === 0 ? (
            <p className="mt-6 border-t border-line pt-6 text-muted">
              No conflicts: none of these investors backed your competitors.
            </p>
          ) : (
            <ul className="mt-6">
              {report.skip.map((s) => (
                <li key={s.investor.id}>
                  <SkipCard item={s} companyId={report.company.id} companyName={report.company.name} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function ListHeading({
  id,
  label,
  count,
  title,
  hint,
}: {
  id: string;
  label: string;
  count: number;
  title: string;
  hint: string;
}) {
  return (
    <div>
      <p className="label text-muted">
        {label} · {count}
      </p>
      <h2 id={id} className="display mt-3 scroll-mt-6 text-5xl md:text-6xl">
        {title}
      </h2>
      <p className="mt-4 max-w-2xl text-muted">{hint}</p>
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
      <p className="label text-muted">Founder report</p>
      <h1 className="display mt-4 text-5xl break-words sm:text-6xl md:text-8xl">{company.name}</h1>
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
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <SourceBadges sources={company.sources} />
        <Link href={prepPath(company)} className="text-sm underline underline-offset-4">
          Meeting investors at Slush? Prep briefs
        </Link>
      </div>
    </header>
  );
}

function LoadingReport() {
  return (
    <div aria-busy="true" aria-live="polite">
      <p className="label text-muted">Founder report</p>
      <div className="mt-4 h-20 w-2/3 max-w-xl animate-pulse bg-surface" />
      <p className="mt-8 max-w-xl text-muted">
        Finding your competitors in Cala, then the rounds they raised and the investors behind
        them.
      </p>
      <SlowNotice />
      <div className="mt-12 flex gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-9 w-28 animate-pulse rounded-[5px] bg-surface" />
        ))}
      </div>
    </div>
  );
}
