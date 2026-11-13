// Investor check (C7): group InvestorCheck.rounds into a market map, one entry
// per company (the startup first, then each competitor), with deduped backers.

import type { Competitor, Conflict, EntityRef, InvestorCheck, Round } from "./types";

export interface Backer {
  investor: EntityRef;
  led: boolean; // led at least one of this company's rounds
}

export interface MarketEntry {
  company: EntityRef;
  competitor: Competitor | null; // null for the startup itself (or an unknown company)
  rounds: Round[]; // dated rounds newest first, then undated
  backers: Backer[]; // leads first, then by name
}

export function marketMap(check: InvestorCheck): MarketEntry[] {
  const byCompany = new Map<string, Round[]>();
  for (const r of check.rounds) {
    const list = byCompany.get(r.company_id) ?? [];
    list.push(r);
    byCompany.set(r.company_id, list);
  }
  const entry = (company: EntityRef, competitor: Competitor | null): MarketEntry => {
    const rounds = sortRounds(byCompany.get(company.id) ?? []);
    byCompany.delete(company.id);
    return { company, competitor, rounds, backers: backersOf(rounds) };
  };

  const entries = [
    entry(check.company, null),
    ...check.competitors.map((c) => entry(c.company, c)),
  ];
  // Rounds of a company that is neither the startup nor a listed competitor: keep them.
  for (const [id, rounds] of byCompany) {
    const sorted = sortRounds(rounds);
    entries.push({
      company: { id, name: "Other company", type: "Company", description: null },
      competitor: null,
      rounds: sorted,
      backers: backersOf(sorted),
    });
  }
  return entries;
}

export function sortRounds(rounds: Round[]): Round[] {
  return [...rounds].sort((a, b) => {
    if (a.date && b.date) return b.date.localeCompare(a.date);
    if (a.date) return -1;
    if (b.date) return 1;
    return 0;
  });
}

export function backersOf(rounds: Round[]): Backer[] {
  const map = new Map<string, Backer>();
  for (const r of rounds) {
    for (const ri of r.investors) {
      const prev = map.get(ri.investor.id);
      map.set(ri.investor.id, { investor: ri.investor, led: Boolean(prev?.led || ri.is_lead) });
    }
  }
  return [...map.values()].sort(
    (a, b) => Number(b.led) - Number(a.led) || a.investor.name.localeCompare(b.investor.name),
  );
}

/** Undated rounds without a label are A7's "backers without round details". */
export function roundTitle(r: Round): string {
  if (!r.label && !r.date && !r.amount_text) return "Round details unknown";
  return r.label ?? "Round";
}

/** The conflict from the investor's side of the table. */
export function investorConflictText(c: Conflict, startupName: string): string {
  if (c.kind === "BOARD") {
    return c.via_person
      ? `${c.via_person.name} sits on the board of ${c.competitor.name}, which competes with ${startupName}`
      : `You have a board seat at ${c.competitor.name}, which competes with ${startupName}`;
  }
  return `${c.competitor.name} is in your portfolio and competes with ${startupName}`;
}
