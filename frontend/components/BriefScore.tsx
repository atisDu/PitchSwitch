"use client";

// The brief's score section: how this investor's fit score adds up, from the company's founder
// report (the brief itself carries no score). One report request per company, shared by every
// brief on the page (Slush prep shows several). Shows nothing until the report is there, or if
// it fails or the investor isn't on it.

import { useEffect, useState } from "react";

import { ScoreBox } from "@/components/InvestorCard";
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
    <div className="mt-10">
      <ScoreBox
        breakdown={breakdown}
        sources={source?.sources ?? []}
        title="How the score adds up"
        note={item.skip ? "Fit despite the conflict; on the Skip list" : "On the Pitch list"}
      />
    </div>
  );
}
