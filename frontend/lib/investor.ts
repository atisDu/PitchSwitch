// Wording for investor cards (C6). Pure, so the rules are unit-tested.

import { formatSourceDate } from "./sources.ts";
import { displayName } from "./format.ts";
import type { Conflict, InvestorScore } from "./types";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** "Leads in your space", honest about how much Cala says about who led. */
export function leadSummary(s: InvestorScore): string {
  const rounds = s.rounds_in_space;
  if (rounds === 0) return "No rounds in your space yet";
  switch (s.lead_data) {
    case "known":
      if (s.leads_in_space === 0) return `In ${plural(rounds, "round")} in your space, none led`;
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

/** The reason an investor is on the Skip list, in one line. `investorId` tells a sanctions
 *  record on the fund itself from one on its LP. */
export function conflictText(c: Conflict, investorId?: string): string {
  if (c.kind === "SANCTION") {
    if (c.competitor.id === investorId) return "Has a sanctions record in Cala";
    if (investorId) return `Its LP ${displayName(c.competitor.name)} has a sanctions record in Cala`;
    return `Sanctions record in Cala on ${displayName(c.competitor.name)}`;
  }
  if (c.kind === "BOARD") {
    return c.via_person
      ? `${c.via_person.name} sits on the board of your competitor ${displayName(c.competitor.name)}`
      : `Has a seat on the board of your competitor ${displayName(c.competitor.name)}`;
  }
  return `Backed your competitor ${displayName(c.competitor.name)}`;
}

/** The B25 screen's line for an investor with no record. Shown plainly, last: absence in Cala is
 *  not proof, so it never reads as "clean". */
export const SCREENED_TEXT = "screened: no sanctions record in Cala";

/** What puts the funds in `skip` on the Skip list, in a clause: "backed a direct competitor",
 *  plus the other kinds that occur. */
export function skipCause(skip: InvestorScore[]): string {
  const kinds = new Set(skip.flatMap((s) => s.conflicts.map((c) => c.kind)));
  const parts: string[] = [];
  if (kinds.has("PORTFOLIO") || kinds.size === 0) parts.push("backed a direct competitor");
  if (kinds.has("BOARD")) parts.push("sit on a competitor's board");
  if (kinds.has("SANCTION")) parts.push("have a sanctions record in Cala");
  return parts.length > 1 ? `${parts.slice(0, -1).join(", ")} or ${parts.at(-1)}` : parts[0];
}
