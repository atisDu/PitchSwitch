// Mock of B21's funding fit (contracts/api.md, "Funding amount") until B ships it. Same shape and
// the same comparison the contract describes, on the round sizes in A's fixtures; B's real
// thresholds may differ. Amounts are whole-round sizes, never one investor's share.

import { formatEuro } from "../lib/money.ts";
import type { FundingFit, Round, Source } from "../lib/types.ts";

function sized(rounds: Round[]): Round[] {
  return rounds.filter((r) => typeof r.amount_eur === "number" && r.amount_eur > 0);
}

function sourcesOf(rounds: Round[]): Source[] {
  return rounds.flatMap((r) => r.sources.slice(0, 1)).slice(0, 3);
}

const range = (rs: Round[]) => {
  const a = rs.map((r) => r.amount_eur as number);
  return { lo: Math.min(...a), hi: Math.max(...a) };
};
const span = (lo: number, hi: number) => (lo === hi ? formatEuro(lo) : `${formatEuro(lo)}–${formatEuro(hi)}`);

/** Founder mode: the raise against the sizes of the rounds this investor has joined. */
export function fitForRaise(target: number, investorName: string, investorRounds: Round[]): FundingFit {
  const rs = sized(investorRounds);
  if (rs.length === 0) {
    return { verdict: "unknown", text: `Cala has no round sizes for ${investorName}'s deals`, sources: [] };
  }
  const { lo, hi } = range(rs);
  const joins = `Joins rounds of ${span(lo, hi)}`;
  if (target < lo / 2) return { verdict: "too_small", text: `${joins}; your ${formatEuro(target)} raise is smaller`, sources: sourcesOf(rs) };
  if (target > hi * 2) return { verdict: "too_large", text: `${joins}; your ${formatEuro(target)} raise is bigger`, sources: sourcesOf(rs) };
  return { verdict: "fits", text: `${joins}; your ${formatEuro(target)} raise fits`, sources: sourcesOf(rs) };
}

/** Investor mode: the most the investor will put in against the company's own round sizes. */
export function fitForCheck(maxCheck: number, companyName: string, companyRounds: Round[]): FundingFit {
  const rs = sized(companyRounds);
  if (rs.length === 0) {
    return { verdict: "unknown", text: `Cala has no round sizes for ${companyName}`, sources: [] };
  }
  const { lo, hi } = range(rs);
  const raised = `${companyName} raised rounds of ${span(lo, hi)}`;
  if (maxCheck > hi) {
    return { verdict: "too_small", text: `${raised}; less than your ${formatEuro(maxCheck)} check`, sources: sourcesOf(rs) };
  }
  if (maxCheck < hi * 0.05) {
    return { verdict: "too_large", text: `${raised}; a ${formatEuro(maxCheck)} check would be a small share`, sources: sourcesOf(rs) };
  }
  return { verdict: "fits", text: `${raised}; a ${formatEuro(maxCheck)} check fits`, sources: sourcesOf(rs) };
}
