"use client";

// Founder report (C5 → C6): company header, competitor chips, then the Pitch and
// Skip lists. Removing competitors and pressing "Re-rank" calls
// /api/founder/analyze again with the remaining `competitor_ids`.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { CompetitorChips } from "@/components/CompetitorChips";
import { SourceBadges } from "@/components/SourceBadge";
import { analyzeFounder, ApiError } from "@/lib/api";
import { keptCompetitorIds, prettyEnum } from "@/lib/format";
import type { Company, FounderReport } from "@/lib/types";

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
  | { status: "ready"; report: FounderReport; reranking: boolean; rerankError: string | null };

export function FounderReportView({ companyId }: { companyId: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [narrowed, setNarrowed] = useState(false); // ranked against a user-edited list
  const abort = useRef<AbortController | null>(null);

  const run = useCallback(
    async (competitorIds?: string[]) => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      setLoad((prev) =>
        prev.status === "ready" && competitorIds
          ? { ...prev, reranking: true, rerankError: null }
          : { status: "loading" },
      );
      try {
        const report = await analyzeFounder(
          { company_id: companyId, ...(competitorIds ? { competitor_ids: competitorIds } : {}) },
          ctrl.signal,
        );
        if (ctrl.signal.aborted) return;
        setLoad({ status: "ready", report, reranking: false, rerankError: null });
        setRemoved(new Set());
        setNarrowed(Boolean(competitorIds));
      } catch (err) {
        if (ctrl.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : "Something went wrong.";
        setLoad((prev) =>
          prev.status === "ready" && competitorIds
            ? { ...prev, reranking: false, rerankError: message }
            : { status: "error", message, notFound: err instanceof ApiError && err.status === 404 },
        );
      }
    },
    [companyId],
  );

  useEffect(() => {
    void run();
    return () => abort.current?.abort();
  }, [run]);

  if (load.status === "loading") return <LoadingReport />;
  if (load.status === "error") {
    return (
      <div className="max-w-xl">
        <p className="label text-muted">Founder report</p>
        <h1 className="display mt-4 text-5xl">
          {load.notFound ? "We couldn't find that company." : "The report didn't load."}
        </h1>
        <p className="mt-6 border-l-2 border-foreground pl-3">{load.message}</p>
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

      <section
        className={`mt-16 border-t border-line pt-8 transition-opacity ${reranking ? "opacity-40" : ""}`}
        aria-busy={reranking}
      >
        {/* C6 replaces this summary with the Pitch and Skip lists. */}
        <p className="label">Investors</p>
        <p className="display mt-4 text-5xl">
          {report.pitch.length} to pitch, {report.skip.length} to skip.
        </p>
      </section>
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
      <h1 className="display mt-4 text-6xl md:text-8xl">{company.name}</h1>
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
      <p className="label text-muted">Founder report</p>
      <div className="mt-4 h-20 w-2/3 max-w-xl animate-pulse bg-surface" />
      <p className="mt-8 max-w-xl text-muted">
        Finding your competitors in Cala, then the rounds they raised and the investors behind
        them. This can take a few seconds.
      </p>
      <div className="mt-12 flex gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-9 w-28 animate-pulse rounded-[5px] bg-surface" />
        ))}
      </div>
    </div>
  );
}
