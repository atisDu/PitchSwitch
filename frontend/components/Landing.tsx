// Landing page (/about). Layout advice from the taste skill (hero alone on screen one, one idea
// per screen, top-aligned headings, equal edges, the product's own UI as the picture, plain copy);
// the look stays frontend/DESIGN.md. Every figure and quote below is live PitchSwitch output for the
// demo company Sensofusion Oy, fetched on 14 Nov 2026 (no invented data).

import Link from "next/link";
import type { ReactNode } from "react";

import { SourceBadge, SourceBadges } from "@/components/SourceBadge";
import { checkPath, founderPath } from "@/lib/routes";
import type { Source } from "@/lib/types";

const SENSOFUSION = "202e9283-6455-486f-8868-03c7e0d0cf29";
const SKYFALL = "9b65ed62-a126-4255-8339-44c59fbf0ad8";

const AAVUUS: Source = {
  name: "aavuus.com",
  url: "https://www.aavuus.com/news/aavuus-raises-pre-seed",
  date: "2026-06-09",
  rank: "PRIMARY",
};
const STENDR_BACKERS: Source[] = [
  { name: "tracxn.com", url: "https://tracxn.com/d/companies/stendr/__7VSvHoLx3hjMEv6yAnnHfm3bFhEeOWBkgqe3NhG5Jbc", date: "2026-08-24", rank: "UNKNOWN" },
  { name: "pitchbook.com", url: "https://pitchbook.com/profiles/company/1376632-18", date: "2026-08-24", rank: "UNKNOWN" },
  { name: "www.crunchbase.com", url: "https://www.crunchbase.com/organization/skyfall-ventures/signals_and_news/timeline", date: "2026-08-24", rank: "UNKNOWN" },
];
const NIF: Source = {
  name: "nif.fund",
  url: "https://www.nif.fund/news/the-nato-innovation-fund-leads-e15mn-series-a-in-kelluu-to-build-europes-persistent-aerial-intelligence-layer-and-strengthen-natos-surveillance-capabilities/",
  date: "2026-04-14",
  rank: "PRIMARY",
};
const VEGVISIR: Source = {
  name: "tracxn.com",
  url: "https://tracxn.com/d/companies/vegvisir/__PbV15XkQ5HDNwjwidwv4gAN2oGWU1gO6VbylguwEJ-E/funding-and-investors",
  date: "2026-08-25",
  rank: "UNKNOWN",
};
const COMPETITORS = ["MyDefence", "Stendr", "Frankenburg Technologies", "Origin Robotics"];
const PITCH = [
  { name: "Maki.vc", fit: 73, line: "Led 2 of 2 rounds in your space · Last lead 9 Jun 2026", reason: "Led Aavuus and Metaktik pre-seeds", source: AAVUUS },
  { name: "NATO Innovation Fund", fit: 49, line: "Led 1 of 1 round in your space · Last lead 14 Apr 2026", reason: "Led Kelluu's Series A", source: NIF },
  { name: "ScaleWolf", fit: 45, line: "In 3 rounds in your space · Cala doesn't say who led", reason: "Took part in Vegvisir, Granta Autonomy, Broswarm", source: VEGVISIR },
];
// The rest of Sensofusion's Skip list, each with the rival it backed (live, 14 Nov).
const SKIP_REST: [string, string][] = [
  ["Skaala Investments", "Frankenburg Technologies"],
  ["Silicon Roundabout Ventures", "Origin Robotics"],
  ["Startuplab Founders", "Stendr"],
  ["Change Ventures", "Origin Robotics"],
  ["NATO", "Frankenburg Technologies"],
  ["Nova Founders Capital", "Frankenburg Technologies"],
  ["Rainfall Ventures", "Stendr"],
  ["SMARTCAP", "Frankenburg Technologies"],
];

export function Landing() {
  return (
    <div className="landing">
      <Hero />
      <Screen id="pitch" label="Founder mode · Pitch">
        <h2 className="display text-5xl md:text-7xl">Who to pitch, ranked by how they invest.</h2>
        <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <div>
            <p className="max-w-md text-lg leading-snug text-muted">
              Every investor behind your competitors&apos; rounds is scored 0 to 100 in plain code,
              with the source for each number one click away.
            </p>
            <dl className="mt-10 divide-y divide-line border-y border-line">
              <Signal term="Leads in your space" weight="25" text="How often they set the terms in rounds like yours." />
              <Signal term="Companies in your space" weight="15" text="Weighted by how close each one is to you." />
              <Signal term="Recency" weight="15" text="How recently they invested in your space." />
              <Signal term="Warm paths" weight="15" text="Funds that already co-invest with your backers." />
              <Signal term="Activity" weight="10" text="Deals in the last 12 months." />
              <Signal term="Stage fit" weight="10" text="How often they invest at your stage or the next." />
              <Signal term="Nordic or Baltic" weight="10" text="Funds based in the region." />
            </dl>
          </div>
          <Frame title="Sensofusion Oy · Pitch · 28">
            <ol className="divide-y divide-line">
              {PITCH.map((p, i) => (
                <li key={p.name} className="grid grid-cols-[2.5rem_1fr_auto] gap-x-4 p-5 md:px-6">
                  <p className="display text-3xl text-muted">{String(i + 1).padStart(2, "0")}</p>
                  <div className="min-w-0">
                    <p className="text-lg font-medium">{p.name}</p>
                    <p className="mt-1 text-sm text-muted">{p.line}</p>
                    <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                      {p.reason} <SourceBadge source={p.source} />
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="display text-4xl text-muted">{p.fit}</p>
                    <div className="mt-2 ml-auto h-1 w-16 bg-surface">
                      <div className="h-1 bg-accent" style={{ width: `${p.fit}%` }} />
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </Frame>
        </div>
      </Screen>

      <Screen id="skip" label="Founder mode · Skip">
        <h2 className="display text-5xl md:text-7xl">The skip list: funds that backed a direct rival.</h2>
        <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <div>
            <p className="max-w-md text-lg leading-snug text-muted">
              Gemini reads the candidates and keeps the direct competitors, each with its reason; you
              remove any that don&apos;t belong and re-rank. Anyone who backed one, or sits on its
              board, goes on Skip.
            </p>
            <p className="label mt-10 text-muted">Sensofusion&apos;s direct competitors</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {COMPETITORS.map((c) => (
                <li key={c} className="rounded-[5px] border border-foreground px-3 py-1.5 text-sm font-medium">
                  {c}
                </li>
              ))}
            </ul>
          </div>
          <Frame title="Sensofusion Oy · Skip · 9">
            <div className="p-5 md:p-6">
              <div className="border-l-4 border-press pl-4">
                <p className="text-xl font-medium">
                  Skyfall Ventures <span className="label ml-2 text-muted">Organization</span>
                </p>
                <p className="mt-3 text-lg leading-snug font-medium">
                  <span className="label mr-2 inline-block rounded-[5px] bg-press px-1.5 py-1 align-middle text-background">
                    Conflict
                  </span>
                  Backed your competitor Stendr
                </p>
                <div className="mt-2">
                  <SourceBadges sources={STENDR_BACKERS} max={2} />
                </div>
              </div>
              <ul className="mt-6 divide-y divide-line border-t border-line text-sm">
                {SKIP_REST.map(([fund, rival]) => (
                  <li key={fund} className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2.5">
                    <span className="font-medium">{fund}</span>
                    <span className="text-muted">backed {rival}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Frame>
        </div>
      </Screen>

      <Screen id="flip" label="Investor mode" dark>
        <h2 className="display text-5xl md:text-7xl">The flip: the same conflict, from the fund&apos;s side.</h2>
        <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <div>
            <p className="max-w-md text-lg leading-snug text-sage">
              A startup pitches you between Slush meetings. Enter your fund and their name: in seconds
              you see whether they compete with your portfolio, and who backed their rivals.
            </p>
            <Link href={checkPath(SKYFALL, SENSOFUSION)} className="btn-primary press mt-10">
              Open the sample check
            </Link>
          </div>
          <div className="lift rounded-[5px] border border-slate bg-slate p-6 md:p-8">
            <p className="label text-sage">Verdict · Skyfall Ventures × Sensofusion Oy</p>
            <p className="display mt-4 text-5xl md:text-6xl">Conflict.</p>
            <p className="mt-5 text-xl leading-snug">Stendr is in your portfolio and competes with Sensofusion Oy.</p>
            <p className="label mt-8 text-sage">Who backed Stendr</p>
            <ul className="mt-3 flex flex-wrap gap-1.5 text-sm">
              <li className="rounded-[5px] border border-sage/40 px-2 py-1">Rainfall Ventures</li>
              <li className="rounded-[5px] border border-foreground bg-accent px-2 py-1 font-medium text-foreground">
                Skyfall Ventures <span className="label ml-1">You</span>
              </li>
              <li className="rounded-[5px] border border-sage/40 px-2 py-1">Startuplab Founders</li>
            </ul>
          </div>
        </div>
      </Screen>

      <Screen id="sources" label="Sources">
        <h2 className="display text-5xl md:text-7xl">Every claim links to its source.</h2>
        <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <div>
            <p className="max-w-md text-lg leading-snug text-muted">
              Facts come only from Cala&apos;s graph of companies, rounds and investors. Each badge
              says how reliable the source is and when it was published.
            </p>
            <dl className="mt-10 divide-y divide-line border-y border-line">
              {(
                [
                  ["PRIMARY", "The company or fund's own announcement"],
                  ["FILING", "A company register or official filing"],
                  ["PRESS", "A news article"],
                  ["AGGREGATOR", "A database that collects funding data"],
                ] as const
              ).map(([rank, text]) => (
                <div key={rank} className="flex items-center gap-4 py-3">
                  <dt className="w-28 shrink-0">
                    <SourceBadge source={{ name: rank, url: null, date: null, rank }} />
                  </dt>
                  <dd className="text-sm text-muted">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
          <Frame title="Brief · Skyfall Ventures × Sensofusion Oy">
            <div className="p-5 md:p-6">
              <p className="label text-muted">Verdict</p>
              <p className="mt-2 text-lg leading-relaxed">
                Skip Skyfall Ventures because it backs Stendr, a direct competitor of Sensofusion Oy.
                {[1, 2, 3].map((n) => (
                  <sup key={n} className="ml-0.5">
                    <span className="rounded-[3px] bg-echo px-1 text-[0.7em] font-medium">{n}</span>
                  </sup>
                ))}
              </p>
              <ol className="mt-6 space-y-2 border-t border-line pt-4">
                {STENDR_BACKERS.map((s, i) => (
                  <li key={s.name} className="flex items-center gap-3 text-sm">
                    <span className="display w-5 text-xl text-muted">{i + 1}</span>
                    <SourceBadge source={s} />
                    <span className="truncate">{s.name}</span>
                  </li>
                ))}
              </ol>
            </div>
          </Frame>
        </div>
      </Screen>

      <Screen id="slush" label="Slush prep and agents">
        <h2 className="display text-5xl md:text-7xl">A brief for every Slush meeting, and an MCP server.</h2>
        <div className="mt-12 grid items-start gap-6 lg:grid-cols-2">
          <article className="lift rounded-[5px] border border-line p-6 md:p-8">
            <p className="label text-muted">Slush prep</p>
            <p className="mt-3 text-lg leading-snug text-muted">
              Paste the funds from your calendar. An agent looks each one up and writes a one-page brief
              where every sentence cites its source.
            </p>
            <div className="mt-6 border border-foreground p-5">
              <div className="flex items-start justify-between gap-3">
                <p className="text-xl font-medium">Lifeline Ventures</p>
                <span className="label rounded-[5px] bg-accent px-1.5 py-1">Brief ready</span>
              </div>
              <p className="mt-3 leading-snug">
                You can pitch Lifeline Ventures because no conflict was found and it led 44 out of
                approximately 105 funding rounds.
              </p>
              <p className="mt-3 text-sm text-muted">29 sources</p>
            </div>
            <Link href="/prep" className="draw mt-6 inline-block text-sm">
              Prep your Slush meetings
            </Link>
          </article>
          <article className="lift rounded-[5px] border border-line p-6 md:p-8">
            <p className="label text-muted">MCP server</p>
            <p className="mt-3 text-lg leading-snug text-muted">
              The same seven tools for Claude Desktop, Claude Code or Cursor, so your own agent can
              check a fund before a meeting.
            </p>
            <div className="mt-6 overflow-hidden rounded-[5px] bg-press p-5 font-mono text-sm leading-relaxed text-background">
              <p className="text-sage">› Using only PitchSwitch, should Sensofusion pitch Skyfall Ventures?</p>
              <p className="mt-3">resolve_company(&quot;Skyfall Ventures&quot;)</p>
              <p>check_conflict(skyfall, sensofusion)</p>
              <p className="mt-3 text-accent">→ PORTFOLIO conflict via Stendr · 7 sources</p>
            </div>
          </article>
        </div>
      </Screen>

      <Screen id="how" label="How it works">
        <h2 className="display text-5xl md:text-7xl">Built on Cala&apos;s graph, four hops deep.</h2>
        <ol className="mt-12 grid gap-px overflow-hidden rounded-[5px] border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Your company", "Resolved to one Cala entity; you confirm which."],
            ["Competitors", "Candidates from Cala, judged by Gemini, removable by you."],
            ["Their rounds", "Every round, amount and lead Cala knows, with sources."],
            ["The investors", "Scored 0 to 100 in plain code: Pitch or Skip."],
            ["Their portfolios", "Any stake in a direct rival is a conflict."],
          ].map(([t, d], i) => (
            <li key={t} className="bg-background p-6">
              <p className="display text-4xl text-muted">{String(i + 1).padStart(2, "0")}</p>
              <p className="mt-6 font-medium">{t}</p>
              <p className="mt-2 text-sm leading-snug text-muted">{d}</p>
            </li>
          ))}
        </ol>
        <ul className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Cala", "The only source of facts"],
            ["Gemini", "Judges competitors, writes briefs"],
            ["MongoDB Atlas", "Shared cache and investor graph"],
            ["Verda", "Hosting and the nightly crawl"],
          ].map(([t, d]) => (
            <li key={t} className="border-t-2 border-foreground pt-4">
              <p className="font-medium">{t}</p>
              <p className="mt-1 text-sm text-muted">{d}</p>
            </li>
          ))}
        </ul>
      </Screen>

      <section className="screen flex flex-col justify-center border-t border-line">
        <h2 className="display max-w-5xl text-6xl md:text-8xl">
          Know who to skip <em>before</em> Slush.
        </h2>
        <div className="mt-12 flex flex-wrap gap-4">
          <Link href="/" className="btn-primary press">
            Check your investors
          </Link>
          <Link href={founderPath(SENSOFUSION)} className="btn-ghost press h-[47px]">
            Open the sample report
          </Link>
        </div>
      </section>
    </div>
  );
}

function Hero() {
  return (
    <section className="screen hero-screen grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <div className="enter">
        <p className="label text-muted">PitchSwitch · for founders and VCs</p>
        <h1 className="display mt-6 text-6xl md:text-8xl">
          Investor screening for founders raising at <em>Slush</em>.
        </h1>
        <p className="mt-8 max-w-xl text-lg leading-snug text-muted">
          PitchSwitch walks Cala&apos;s graph from your company to its competitors, their rounds and
          the funds behind them, then tells you who to pitch and who to skip, with a source on every
          claim.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link href="/" className="btn-primary press">
            Check your investors
          </Link>
          <Link href={founderPath(SENSOFUSION)} className="btn-ghost press h-[47px]">
            Open the sample report
          </Link>
        </div>
      </div>
      <div className="enter enter-late">
        <Frame title="Sensofusion Oy · Founder report">
          <div className="grid grid-cols-3 divide-x divide-line border-b border-line">
            {[
              ["4", "direct competitors"],
              ["28", "funds to pitch"],
              ["9", "funds to skip"],
            ].map(([n, t]) => (
              <div key={t} className="p-5">
                <p className="display text-5xl">{n}</p>
                <p className="label mt-2 text-muted">{t}</p>
              </div>
            ))}
          </div>
          <div className="p-5">
            <div className="border-l-4 border-press pl-4">
              <p className="font-medium">Skyfall Ventures</p>
              <p className="mt-2 leading-snug">
                <span className="label mr-2 inline-block rounded-[5px] bg-press px-1.5 py-1 align-middle text-background">
                  Conflict
                </span>
                Backed your competitor Stendr
              </p>
              <div className="mt-2">
                <SourceBadges sources={STENDR_BACKERS} max={2} />
              </div>
            </div>
          </div>
          <div className="flex items-start justify-between gap-4 border-t border-line p-5">
            <div className="border-l-4 border-accent pl-4">
              <p className="label text-muted">Pitch first</p>
              <p className="mt-1 font-medium">Maki.vc</p>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
                Led 2 of 2 rounds in your space <SourceBadge source={AAVUUS} />
              </p>
            </div>
            <div className="text-right">
              <p className="display text-4xl text-muted">73</p>
              <p className="label mt-1 text-muted">Fit / 100</p>
            </div>
          </div>
        </Frame>
      </div>
    </section>
  );
}

function Screen({
  id,
  label,
  dark = false,
  children,
}: {
  id: string;
  label: string;
  dark?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-label={label}
      className={`screen ${dark ? "dark-band bg-press text-background" : "border-t border-line"}`}
    >
      <p className={`label ${dark ? "text-sage" : "text-muted"}`}>{label}</p>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function Frame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="lift overflow-hidden rounded-[5px] border border-foreground bg-background text-foreground">
      <div className="flex items-center gap-2 border-b border-foreground px-4 py-2.5">
        <span className="h-2 w-2 rounded-full bg-line" />
        <span className="h-2 w-2 rounded-full bg-line" />
        <span className="h-2 w-2 rounded-full bg-accent" />
        <span className="label ml-3 truncate text-muted">{title}</span>
      </div>
      {children}
    </div>
  );
}

function Signal({ term, weight, text }: { term: string; weight: string; text: string }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-x-4 py-4">
      <dt className="font-medium">{term}</dt>
      <dd className="display row-span-2 text-3xl text-muted">{weight}</dd>
      <dd className="mt-1 text-sm text-muted">{text}</dd>
    </div>
  );
}
