// The sample report the landing page links to: made-up companies, funds, rounds and sources (the
// same names as /about), served by lib/api.ts for any ID that starts with "sample-", so the
// report, check, brief and chat pages run on it without a backend. Nothing here is real data.

import type {
  AgentEvent,
  Brief,
  Company,
  Competitor,
  Conflict,
  EntityRef,
  FounderReport,
  InvestorCheck,
  InvestorScore,
  Reason,
  Round,
  Source,
} from "./types";
import { parseBreakdown } from "./score.ts";

export const SAMPLE_COMPANY_ID = "sample-norvale";
export const isSample = (id: string | null | undefined) => !!id && id.startsWith("sample-");

const slug = (name: string) =>
  name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
const src = (name: string, date: string, rank: Source["rank"] = "PRESS"): Source => ({ name, url: null, date, rank });
const ref = (name: string, type: string, description: string): EntityRef => ({ id: `sample-${slug(name)}`, name, type, description });

const COMPANY: Company = {
  ...ref("Norvale Sensing Oy", "Organization", "A made-up company for this sample: a Finnish counter-drone startup building multi-sensor detection for airports and critical sites."),
  id: SAMPLE_COMPANY_ID,
  industries: ["AEROSPACE_AND_DEFENSE"],
  stage: "Seed",
  country: "Finland",
  total_funding_text: "~€1.2M (Pre-Seed, March 2025)",
  sources: [src("registry.example", "2026-09-25", "FILING")],
};

function competitor(name: string, country: string, stage: string | null, desc: string, reason: string, similarity: number): Competitor {
  return {
    company: { ...ref(name, "Company", desc), industries: ["AEROSPACE_AND_DEFENSE"], stage, country, total_funding_text: null, sources: [src("startupnews.example", "2026-08-24")] },
    reason,
    similarity,
  };
}

const COMPETITORS: Competitor[] = [
  competitor("Brakka Defence", "Denmark", "Series A", "Danish maker of radio-frequency drone detectors.", "Same market: drone detection for airports and military sites.", 0.86),
  competitor("Hjelmvik", "Norway", "Pre-Seed", "Norwegian startup building an AI multi-sensor platform for drone defence.", "Both build multi-sensor counter-drone hardware and software for detection and tracking.", 0.88),
  competitor("Talvio Technologies", "Estonia", "Seed", "Estonian developer of radar and camera fusion for perimeter security.", "Same segment: sensor fusion to detect small drones.", 0.83),
  competitor("Ostravia Robotics", "Latvia", "Seed", "Latvian maker of autonomous interceptor drones.", "Same buyers and use case: protecting sites from hostile drones.", 0.81),
];
const comp = (name: string) => COMPETITORS.find((c) => c.company.name === name)!.company;
const compRef = (name: string): EntityRef => {
  const { id, type, description } = comp(name);
  return { id, name, type, description };
};

// The competitors' rounds, which is where the Skip list's conflicts come from.
const R = (company: string, label: string, date: string, amount: string, eur: number, backers: [string, boolean | null][], sources: Source[]): Round => ({
  id: `sample-round-${slug(company)}-${date}`,
  company_id: company === COMPANY.name ? COMPANY.id : comp(company).id,
  label,
  date,
  amount_text: amount,
  amount_eur: eur,
  investors: backers.map(([n, lead]) => ({ investor: ref(n, "Organization", `A made-up fund for this sample.`), is_lead: lead })),
  sources,
});
const ROUNDS: Round[] = [
  R("Norvale Sensing Oy", "Pre-Seed", "2025-03-12", "~€1.2M", 1_200_000, [["Polku Angels", true]], [src("registry.example", "2025-03-14", "FILING")]),
  R("Hjelmvik", "Pre-Seed", "2026-04-08", "$5.4M", 5_000_000, [["Rainmere Ventures", null], ["Fjordline Ventures", null], ["Startpoint Founders AS", null]], [src("dealwire.example", "2026-08-24", "AGGREGATOR"), src("fundingdesk.example", "2026-08-24", "AGGREGATOR"), src("startupnews.example", "2026-04-08")]),
  R("Ostravia Robotics", "Seed", "2025-11-18", "€3M", 3_000_000, [["Bridgewell Ventures", true], ["Gráfell Capital", false]], [src("vcdigest.example", "2025-11-18", "UNKNOWN"), src("startupnews.example", "2025-11-19")]),
  R("Talvio Technologies", "Seed", "2026-02-03", "€4M", 4_000_000, [["Allied Defence Fund", true], ["Noventa Founders Capital", false], ["Saaren Investments OÜ", false], ["Smallcap North", false]], [src("talvio.example", "2026-02-03", "PRIMARY"), src("dealwire.example", "2026-02-05", "AGGREGATOR")]),
];

const NORDIC = new Set(["Finland", "Sweden", "Norway", "Denmark", "Iceland", "Estonia", "Latvia", "Lithuania"]);
const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));
const PORTFOLIO = ["Pellava Labs", "Routa Aero", "Siivu Systems", "Kajo Optics", "Vartio Robotics", "Tuisku Labs"];
const LABELS = ["Pre-Seed", "Seed", "Seed", "Series A"];
const DATES = ["2026-06-09", "2026-03-21", "2025-12-02", "2025-10-14", "2025-07-30", "2025-04-17"];
const PUBLISHERS = ["dealwire.example", "fundingdesk.example", "startupnews.example", "vcdigest.example"];

interface Parts {
  leads: [number, number]; // points, rounds led
  companies: [number, number]; // points, companies in the space
  recency: [number, string];
  activity: [number, number]; // points, deals in 12 months
  warm: [number, number];
  stage: [number, string];
}

/** An investor's score with its breakdown line in the scorer's format (lib/score.ts parses it). */
function score(name: string, country: string, p: Parts, facts: Reason[], conflicts: Conflict[] = []): InvestorScore {
  const geo = NORDIC.has(country) ? 10 : 0;
  const total = p.leads[0] + p.companies[0] + p.recency[0] + p.activity[0] + p.warm[0] + p.stage[0] + geo;
  const line =
    `Score ${fmt(total)}/100 = leads ${fmt(p.leads[0])}/25 (${p.leads[1]} led) + companies here ${fmt(p.companies[0])}/15 (${p.companies[1]})` +
    ` + recency ${fmt(p.recency[0])}/15 (${p.recency[1]}) + activity ${fmt(p.activity[0])}/10 (${p.activity[1]} in 12 mo)` +
    ` + warm paths ${fmt(p.warm[0])}/15 (${p.warm[1]}) + stage fit ${fmt(p.stage[0])}/10 (${p.stage[1]}) + Nordic/Baltic ${geo}/10 (${country})`;
  const sources = facts.flatMap((f) => f.sources).slice(0, 3);
  const led = p.leads[1];
  return {
    investor: ref(name, "Organization", `A made-up ${country === "Finland" ? "Finnish" : country} fund for this sample.`),
    score: Math.round(total * 10) / 10,
    conflicts,
    leads_in_space: led,
    rounds_in_space: Math.max(led, p.companies[1]),
    lead_data: "known",
    last_lead_date: led > 0 ? p.recency[1].replace(/^last lead here /, "") : null,
    deals_last_12m: p.activity[1],
    warm_paths: [],
    reasons: [{ text: line, sources }, ...facts],
    funding_fit: null,
  };
}

/** A fund with one round in the space, its points spread over the signals to reach `target`. */
function filler(
  name: string,
  country: string,
  target: number,
  i: number,
  conflicts: Conflict[] = [],
  round?: Round, // the round in the space it took part in (a Skip fund: the competitor's)
): InvestorScore {
  let left = Math.max(0, target - (NORDIC.has(country) ? 10 : 0));
  const take = (cap: number) => {
    const t = Math.min(cap, left);
    left -= t;
    return Math.round(t * 10) / 10;
  };
  const companies = take(7.5);
  const recency = take(10);
  const activity = take(10);
  const stage = take(10);
  const warm = take(15);
  const co = round ? COMPETITORS.find((c) => c.company.id === round.company_id)!.company.name : PORTFOLIO[i % PORTFOLIO.length];
  const label = round?.label ?? LABELS[i % LABELS.length];
  const date = round?.date ?? DATES[i % DATES.length];
  const fact: Reason = {
    text: `Took part in 1 round in this space: ${co} ${label} (${date})`,
    sources: round?.sources ?? [src(PUBLISHERS[i % PUBLISHERS.length], date)],
  };
  return score(
    name,
    country,
    {
      leads: [0, 0],
      companies: [companies, 1],
      recency: [recency, recency > 0 ? `last round here ${date}` : "no dated round here"],
      activity: [activity, Math.round((activity / 10) * 6)],
      warm: [warm, warm > 0 ? 1 : 0],
      stage: [stage, `${stage > 0 ? 1 : 0} of 1 round at Seed-Series A`],
    },
    [fact],
    conflicts,
  );
}

const KAAMOS = score(
  "Kaamos Ventures",
  "Finland",
  {
    leads: [25, 2],
    companies: [11.3, 2],
    recency: [15, "last lead here 2026-06-09"],
    activity: [8.3, 5],
    warm: [0, 0],
    stage: [0, "0 of 2 rounds at Seed-Series A"],
  },
  [
    { text: "Led 2 rounds in this space: Pellava Labs Pre-Seed (2026-06-09), Routa Aero Pre-Seed (2025-10-02)", sources: [src("pellava.example", "2026-06-09", "PRIMARY"), src("startupnews.example", "2026-06-10")] },
    { text: "Last led a round on 2026-06-09 (Pre-Seed)", sources: [src("pellava.example", "2026-06-09", "PRIMARY")] },
    { text: "5 rounds in the last 12 months", sources: [src("dealwire.example", "2026-10-30", "AGGREGATOR")] },
  ],
);
const LUMO = score(
  "Lumo Seed",
  "Finland",
  {
    leads: [0, 0],
    companies: [7.5, 1],
    recency: [8.5, "last round here 2025-11-20"],
    activity: [5, 3],
    warm: [0, 0],
    stage: [5, "1 of 2 rounds at Seed-Series A"],
  },
  [{ text: "Took part in 1 round in this space: Kajo Optics Seed (2025-11-20)", sources: [src("fundingdesk.example", "2025-11-21", "AGGREGATOR")] }],
);

const PITCH_FUNDS: [string, string, number][] = [
  ["Tundrafold Capital", "Norway", 34], ["Harmaja Partners", "Finland", 32], ["Saukko Capital", "Finland", 30],
  ["Brightfjord Partners", "Sweden", 28], ["Ankkuri Ventures", "Finland", 27], ["Kallio Seed", "Finland", 25],
  ["Rannikko Capital", "Finland", 24], ["Northgale Partners", "United Kingdom", 22], ["Halla Capital", "Finland", 21],
  ["Kuusi Ventures", "Finland", 20], ["Ilmari Seed", "Estonia", 19], ["Vesper Nordic", "Denmark", 18],
  ["Graniitti Capital", "Finland", 17], ["Ruska Ventures", "Finland", 15], ["Laituri Capital", "Finland", 14],
  ["Kotka Seed Fund", "Finland", 13], ["Merivirta Ventures", "Sweden", 12], ["Sisu Bridge Capital", "Germany", 11],
  ["Alder Coast Ventures", "Netherlands", 9], ["Pakkanen Partners", "Finland", 8], ["Vaara Capital", "Norway", 7],
  ["Tähti Seed", "Estonia", 6], ["Kivi & Co Ventures", "Latvia", 5], ["Polku Angels", "Finland", 4],
];

// Skip: each backed a competitor in ROUNDS; the number is its fit despite the conflict.
const SKIP_FUNDS: [string, string, number, string][] = [
  ["Fjordline Ventures", "Norway", 17, "Hjelmvik"], ["Bridgewell Ventures", "United Kingdom", 12, "Ostravia Robotics"],
  ["Startpoint Founders AS", "Norway", 9, "Hjelmvik"], ["Noventa Founders Capital", "Germany", 8, "Talvio Technologies"],
  ["Saaren Investments OÜ", "Estonia", 7, "Talvio Technologies"], ["Allied Defence Fund", "Belgium", 6, "Talvio Technologies"],
  ["Gráfell Capital", "Iceland", 5, "Ostravia Robotics"], ["Rainmere Ventures", "Sweden", 5, "Hjelmvik"],
  ["Smallcap North", "Lithuania", 4, "Talvio Technologies"],
];

const byScore = (a: InvestorScore, b: InvestorScore) => b.score - a.score;
const PITCH = [KAAMOS, LUMO, ...PITCH_FUNDS.map(([n, c, s], i) => filler(n, c, s, i + 2))].sort(byScore);
const SKIP = SKIP_FUNDS.map(([n, c, s, rival], i) => {
  const round = ROUNDS.find((r) => r.company_id === comp(rival).id)!;
  return filler(n, c, s, i, [{ kind: "PORTFOLIO", competitor: compRef(rival), via_person: null, sources: round.sources }], round);
}).sort(byScore);

/** The sample founder report; with `competitorIds`, funds whose only conflicts were removed move to Pitch. */
export function sampleReport(competitorIds?: string[]): FounderReport {
  const kept = competitorIds ? new Set(competitorIds) : null;
  const keep = (s: InvestorScore) => ({ ...s, conflicts: s.conflicts.filter((c) => !kept || kept.has(c.competitor.id)) });
  const skip = SKIP.map(keep);
  return {
    company: COMPANY,
    competitors: COMPETITORS.filter((c) => !kept || kept.has(c.company.id)),
    pitch: [...PITCH, ...skip.filter((s) => s.conflicts.length === 0)].sort(byScore),
    skip: skip.filter((s) => s.conflicts.length > 0),
  };
}

const findScore = (investorId: string) => [...PITCH, ...SKIP].find((s) => s.investor.id === investorId) ?? null;

/** The sample investor check: the fund's conflicts with Norvale, and every competitor's rounds. */
export function sampleCheck(investorId: string): InvestorCheck | null {
  const s = findScore(investorId);
  if (!s) return null;
  return { investor: s.investor, company: COMPANY, conflicts: s.conflicts, competitors: COMPETITORS, rounds: ROUNDS, funding_fit: null };
}

/** `[n]` markers for `sources`, adding each new source to `citations` once (same name and date = same source). */
const citer = (citations: Source[]) => (sources: Source[]) =>
  sources
    .map((x) => {
      const n = citations.findIndex((c) => c.name === x.name && c.date === x.date);
      return `[${n >= 0 ? n + 1 : citations.push(x)}]`;
    })
    .join("");

/** A sample brief built from the fund's score: verdict, conflicts, what it did in the space. */
export function sampleBrief(investorId: string): Brief | null {
  const s = findScore(investorId);
  if (!s) return null;
  const citations: Source[] = [];
  const cite = citer(citations);
  const name = s.investor.name;
  const lines = [`# ${name} × ${COMPANY.name}`, "", "*A sample brief: the companies, funds and sources are made up.*", ""];
  const first = s.conflicts[0];
  lines.push(
    first
      ? `**Verdict: skip.** ${name} backs ${first.competitor.name}, a direct competitor ${cite(first.sources)}.`
      : `**Verdict: worth a pitch.** No tie to your direct competitors found.`,
  );
  const more = s.conflicts.slice(1); // the first is in the verdict
  if (more.length) {
    lines.push("", "## Other conflicts", ...more.map((c) => `- Backs ${c.competitor.name}, a direct competitor ${cite(c.sources)}.`));
  }
  const facts = s.reasons.slice(1);
  if (facts.length) lines.push("", "## Activity in your space", ...facts.map((f) => `- ${f.text} ${cite(f.sources)}.`));
  return { investor_id: s.investor.id, company_id: COMPANY.id, markdown: lines.join("\n"), citations };
}

const PART_LABEL: Record<string, string> = {
  leads: "Leads rounds in this space",
  "companies here": "Companies in your space",
  recency: "Recent activity here",
  activity: "Deals in the last 12 months",
  "warm paths": "Warm paths",
  "stage fit": "Backs your stage",
  "Nordic/Baltic": "Nordic or Baltic fund",
};

/** "Deeper analysis" on the sample: strong and weak points from the fund's own score and facts. */
function sampleDeeper(investorId: string): { text: string; citations: Source[] } | null {
  const s = findScore(investorId);
  const b = s && parseBreakdown(s.reasons[0].text);
  if (!s || !b) return null;
  const citations: Source[] = [];
  const cite = (sources: Source[]) => citer(citations)(sources.slice(0, 2));
  const scoreCite = cite(s.reasons[0].sources);
  const label = (n: string) => PART_LABEL[n] ?? n;
  const strong = [
    ...b.parts.filter((p) => p.got / p.max >= 0.6).map((p) => `- ${label(p.name)}: ${fmt(p.got)} of ${p.max} points (${p.detail}) ${scoreCite}.`),
    ...s.reasons.slice(1).map((f) => `- ${f.text} ${cite(f.sources)}.`),
  ];
  const weak = [
    ...s.conflicts.map((c) => `- It backs ${c.competitor.name}, a direct competitor: a pitch would reach a rival's backer ${cite(c.sources)}.`),
    ...b.parts.filter((p) => p.got === 0).map((p) => `- ${label(p.name)}: no points (${p.detail}).`),
  ];
  const approach = s.conflicts.length
    ? `Leave ${s.investor.name} out of this round, or ask openly how they handle ${s.conflicts[0].competitor.name} before you share the deck.`
    : s.score >= 50
      ? `Lead with what you share with the companies it already backs here, and ask for a first meeting at Slush.`
      : `A warm introduction will matter more than the deck: look for a founder it backed in this space.`;
  const text = [
    "*Sample analysis: the companies, funds and sources are made up.*",
    "## Strong points",
    ...(strong.length ? strong : ["- None stand out in the data."]),
    "## Weak points",
    ...(weak.length ? weak : ["- None stand out in the data."]),
    "## How to approach them",
    approach,
  ].join("\n");
  return { text, citations };
}

/** Chat on a sample page: "Deeper analysis" is answered from the sample; anything else says it's a sample. */
export async function* sampleChat(message: string, investorId?: string): AsyncGenerator<AgentEvent> {
  const event = { message: null, brief: null, investor_name: null, investor: null, citations: [] };
  const deeper = message.startsWith("Deeper analysis") && investorId ? sampleDeeper(investorId) : null;
  yield {
    ...event,
    type: "text",
    message:
      deeper?.text ??
      "This is a sample with made-up companies and funds, so there is nothing to look up. Run a check on your own company to ask about it.",
  };
  yield { ...event, type: "done", citations: deeper?.citations ?? [] };
}
