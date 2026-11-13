// Wording for investor cards (C6). Pure, so the rules are unit-tested.

import { formatSourceDate } from "./sources.ts";
import type { Conflict, InvestorScore } from "./types";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** "Leads in your space", honest about how much Cala says about who led. */
export function leadSummary(s: InvestorScore): string {
  const rounds = s.rounds_in_space;
  if (rounds === 0) return "No rounds in your space yet";
  switch (s.lead_data) {
    case "known":
      return `Led ${s.leads_in_space} of ${plural(rounds, "round")} in your space`;
    case "partial":
      return `Led at least ${s.leads_in_space} of ${plural(rounds, "round")} in your space (lead known for some)`;
    default:
      return `In ${plural(rounds, "round")} in your space · Cala doesn't say who led`;
  }
}

/** "Still active": last lead and deal count, skipping what's unknown. */
export function activitySummary(s: InvestorScore): string {
  const last = formatSourceDate(s.last_lead_date);
  const parts = [last ? `Last lead ${last}` : "No lead on record"];
  if (s.deals_last_12m !== null) parts.push(`${plural(s.deals_last_12m, "deal")} in the last 12 months`);
  return parts.join(" · ");
}

/** The reason an investor is on the Skip list, in one line. */
export function conflictText(c: Conflict): string {
  if (c.kind === "BOARD") {
    return c.via_person
      ? `${c.via_person.name} sits on the board of your competitor ${c.competitor.name}`
      : `Has a seat on the board of your competitor ${c.competitor.name}`;
  }
  return `Backed your competitor ${c.competitor.name}`;
}
