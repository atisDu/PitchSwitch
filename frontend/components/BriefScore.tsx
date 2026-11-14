"use client";

// The brief's score section: how this investor's fit score adds up, from the company's founder
// report (the brief itself carries no score). One report request per company, shared by every
// brief on the page (Slush prep shows several). Shows nothing until the report is there, or if
// it fails or the investor isn't on it.

import { useEffect, useState } from "react";

import { BreakdownRows } from "@/components/InvestorCard";
import { analyzeFounder } from "@/lib/api";
import { splitReasons } from "@/lib/score";
import type { FounderReport, InvestorScore } from "@/lib/types";

const reports = new Map<string, Promise<FounderReport>>();

function report(companyId: string): Promise<FounderReport> {
  let p = reports.get(companyId);
  if (!p) {
    p = analyzeFounder({ company_id: companyId });
    p.catch(() => reports.delete(companyId)); // a failed load is tried again next time
    reports.set(companyId, p);
  }
  return p;
}

export function BriefScore({ investorId, companyId }: { investorId: string; companyId: string }) {
  const [item, setItem] = useState<{ score: InvestorScore; skip: boolean } | null>(null);

  useEffect(() => {
    let live = true;
    report(companyId).then(
      (r) => {
        const skip = r.skip.find((s) => s.investor.id === investorId);
        const found = skip ?? r.pitch.find((s) => s.investor.id === investorId);
        if (live && found) setItem({ score: found, skip: !!skip });
      },
      () => {},
    );
    return () => {
      live = false;
    };
  }, [investorId, companyId]);

  const { breakdown, source } = item ? splitReasons(item.score.reasons) : { breakdown: null, source: null };
  if (!item || !breakdown) return null;
  return (
    <section className="mt-10 border-t border-line pt-6" aria-labelledby={`score-${investorId}`}>
      <h2 id={`score-${investorId}`} className="label text-muted">
        How the score adds up
      </h2>
      <p className="mt-3 flex flex-wrap items-baseline gap-x-3 text-lg">
        <span className="display text-4xl text-accent">{Math.round(breakdown.total)}</span>
        <span className="text-muted">
          of {breakdown.outOf}
          {item.skip ? ", fit despite the conflict: on the Skip list" : ", on the Pitch list"}
        </span>
      </p>
      <BreakdownRows breakdown={breakdown} sources={source?.sources ?? []} />
    </section>
  );
}
