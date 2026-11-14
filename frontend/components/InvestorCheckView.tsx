"use client";

// Investor check (C7): verdict first (conflict or not), then the market map:
// the startup and each competitor with who backed it and its round history.

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";
import { AmountField, FundingFitLine } from "@/components/FundingFit";
import { SlowNotice } from "@/components/SlowNotice";
import { SourceBadges } from "@/components/SourceBadge";
import { describeError } from "@/lib/errors";
import { checkInvestor } from "@/lib/api";
import { investorConflictText, marketMap, roundTitle, type MarketEntry } from "@/lib/check";
import { displayName, investorKind, possessive, prettyEnum } from "@/lib/format";
import { founderPath } from "@/lib/routes";
import { formatSourceDate } from "@/lib/sources";
import type { InvestorCheck, Round, Source } from "@/lib/types";

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean; detail: string | null }
  | { status: "ready"; check: InvestorCheck };

export function InvestorCheckView({
  investorId,
  companyId,
  initialMaxCheck = null,
}: {
  investorId: string;
  companyId: string;
  initialMaxCheck?: number | null; // ?check= in the URL (C18)
}) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0); // "Try again" bumps this to refetch
  const [maxCheck, setMaxCheck] = useState<number | null>(initialMaxCheck); // the most the fund puts in (B21)
  const [updating, setUpdating] = useState(false); // a new amount is being checked; keep the page

  useEffect(() => {
    const ctrl = new AbortController();
    checkInvestor(
      { investor_id: investorId, company_id: companyId, ...(maxCheck ? { max_check_eur: maxCheck } : {}) },
      ctrl.signal,
    ).then(
      (check) => {
        if (ctrl.signal.aborted) return;
        setLoad({ status: "ready", check });
        setUpdating(false);
      },
      (err: unknown) => {
        if (ctrl.signal.aborted) return;
        const e = describeError(err);
        setLoad({ status: "error", message: e.message, notFound: e.notFound, detail: e.detail });
        setUpdating(false);
      },
    );
    return () => ctrl.abort();
  }, [investorId, companyId, attempt, maxCheck]);

  // A new amount is kept in the URL (?check=) and re-checked; the page stays while it loads.
  function applyMaxCheck(amount: number | null) {
    const url = new URL(window.location.href);
    if (amount) url.searchParams.set("check", String(amount));
    else url.searchParams.delete("check");
    window.history.replaceState(null, "", url);
    setUpdating(true);
    setMaxCheck(amount);
  }

  if (load.status === "loading") {
    return (
      <div aria-busy="true" aria-live="polite">
        <div className="h-20 w-2/3 max-w-xl animate-pulse bg-surface" />
        <p className="mt-8 max-w-xl text-muted">
          Comparing your portfolio with this startup&apos;s competitors in Cala, and pulling who
          backed each of them.
        </p>
        <SlowNotice />
      </div>
    );
  }
  if (load.status === "error") {
    return (
      <div className="max-w-xl">
        <h1 className="display text-5xl">
          {load.notFound ? "We couldn't check that pair." : "The check didn't load."}
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
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                setLoad({ status: "loading" });
                setAttempt((n) => n + 1);
              }}
            >
              Try again
            </button>
          )}
          <Link href="/start" className="btn-ghost h-control-lg">
            Search again
          </Link>
        </div>
      </div>
    );
  }

  const { check } = load;
  const { investor, company, conflicts } = check;
  const fund = displayName(investor.name);
  const startup = displayName(company.name);
  const map = marketMap(check);
  const facts = [
    company.stage,
    company.country,
    ...company.industries.map(prettyEnum),
    company.total_funding_text && `${company.total_funding_text} raised`,
  ].filter(Boolean) as string[];

  return (
    <div>
      <title>{`${startup} × ${fund} · Investor check · PitchSwitch`}</title>
      <ChatPanel
        companyId={company.id}
        investorId={investor.id}
        scope={`${fund} × ${startup}`}
        suggestions={[
          `Who led ${possessive(startup)} last round?`,
          `Who backed ${possessive(startup)} competitors?`,
          `What has ${fund} led in this space recently?`,
        ]}
      />
      <header>
        <p className="inline-flex h-8 items-center rounded-full border border-line bg-white px-3 text-[13px] text-muted">
          Investor check
        </p>
        <p className="mt-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-lg">
          <span className="text-muted">Checking as</span>
          <span className="border-b-2 border-accent font-medium">{fund}</span>
          <span className="label text-muted">{investorKind(investor.type)}</span>
          <Link href="/start" className="text-sm text-muted underline underline-offset-4 hover:text-foreground">
            Not your fund?
          </Link>
        </p>
        <h1 className="display mt-4 text-5xl break-words sm:text-6xl md:text-7xl">{startup}</h1>
        {facts.length > 0 && (
          <p className="label mt-6 flex flex-wrap gap-x-4 gap-y-1 text-muted">
            {facts.map((f) => (
              <span key={f}>{f}</span>
            ))}
          </p>
        )}
        {company.description && <p className="mt-4 max-w-2xl text-lg leading-snug">{company.description}</p>}
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <SourceBadges sources={company.sources} />
          <Link href={founderPath(company.id)} className="text-sm underline underline-offset-4">
            See {possessive(startup)} founder view
          </Link>
        </div>
        <div
          className={`mt-8 max-w-xl transition-opacity ${updating ? "opacity-40" : ""}`}
          aria-busy={updating}
        >
          <AmountField side="investor" value={maxCheck} onApply={applyMaxCheck} disabled={updating} />
          {maxCheck !== null && !updating && (
            <div className="mt-3">
              {check.funding_fit ? (
                <FundingFitLine fit={check.funding_fit} side="investor" />
              ) : (
                <p className="text-sm text-muted">
                  Fit by round size isn&apos;t available on this server yet; it will show here once it is.
                </p>
              )}
            </div>
          )}
        </div>
      </header>

      {conflicts.length > 0 ? (
        <section className="mt-12 rounded-[20px] bg-press px-6 py-10 text-background md:px-10 md:py-14" aria-labelledby="verdict">
          <h2 id="verdict" className="display text-5xl md:text-6xl">
            Conflict.
          </h2>
          <ul className="mt-8 space-y-6">
            {conflicts.map((c, i) => (
              <li key={`${c.competitor.id}-${c.kind}-${i}`}>
                <p className="max-w-3xl text-xl leading-snug">{investorConflictText(c, startup)}</p>
                <div className="mt-2">
                  <SourceBadges sources={c.sources} max={3} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section className="window mt-12 border-t-4 border-t-accent p-6 md:p-10" aria-labelledby="verdict">
          <h2 id="verdict" className="display text-4xl md:text-5xl">
            No conflict found.
          </h2>
          <p className="mt-4 max-w-2xl text-muted">
            None of {possessive(startup)} {check.competitors.length} competitors is in {possessive(fund)}{" "}
            portfolio in Cala, and no board links were found. Cala&apos;s portfolio data can be
            incomplete, so check anything that looks off.
          </p>
        </section>
      )}

      <section className="mt-20" aria-labelledby="map-heading">
        <h2 id="map-heading" className="display text-4xl md:text-5xl">
          Who backed the rivals
        </h2>
        <p className="mt-4 max-w-2xl text-muted">
          {startup} and its {check.competitors.length} competitors, with every investor Cala links to them and their
          round history. Leads are marked; your fund is highlighted.
        </p>
        <div className="mt-8">
          {map.map((e) => (
            <MarketCard key={e.company.id} entry={e} isStartup={e.company.id === company.id} investorId={investor.id} />
          ))}
        </div>
      </section>
    </div>
  );
}

function MarketCard({ entry, isStartup, investorId }: { entry: MarketEntry; isStartup: boolean; investorId: string }) {
  const { company, competitor, rounds, backers } = entry;
  const c = competitor?.company;
  const meta = c ? [c.stage, c.country].filter(Boolean).join(" · ") : "";
  return (
    <article className="window mb-3 grid gap-x-10 gap-y-4 p-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] md:p-7">
      <div>
        <p className="label text-muted">{isStartup ? "The startup" : competitor ? "Competitor" : "Other"}</p>
        <h3 className="mt-2 text-2xl font-medium tracking-tight">{displayName(company.name)}</h3>
        {meta && <p className="label mt-2 text-muted">{meta}</p>}
        {competitor && (
          <p className="mt-3 text-sm leading-snug">
            {competitor.reason} <span className="label ml-1 text-muted">AI judgement</span>
          </p>
        )}
        {c && c.sources.length > 0 && (
          <div className="mt-3">
            <SourceBadges sources={c.sources} />
          </div>
        )}
      </div>

      <div>
        <p className="label">Backed by · {backers.length}</p>
        {backers.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            {isStartup
              ? `Cala lists no investors for ${displayName(company.name)} yet.`
              : "Cala lists no investors for this company."}
          </p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {backers.map((b) => {
              const you = b.investor.id === investorId;
              return (
                <li
                  key={b.investor.id}
                  className={`rounded-lg border px-2 py-1 text-sm ${
                    you ? "border-accent bg-echo font-medium" : "border-foreground/15 bg-white"
                  }`}
                >
                  {displayName(b.investor.name)}
                  {b.led && <span className="label ml-1.5">Lead</span>}
                  {you && <span className="label ml-1.5">You</span>}
                </li>
              );
            })}
          </ul>
        )}

        <p className="label mt-6">Rounds · {rounds.length}</p>
        {rounds.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No rounds in Cala.</p>
        ) : (
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {rounds
              .filter((r) => roundTitle(r) !== "Round details unknown")
              .map((r) => (
                <RoundRow key={r.id} round={r} investorId={investorId} />
              ))}
            <UnknownRounds rounds={rounds.filter((r) => roundTitle(r) === "Round details unknown")} investorId={investorId} />
          </ul>
        )}
      </div>
    </article>
  );
}

function RoundRow({ round, investorId }: { round: Round; investorId: string }) {
  const date = formatSourceDate(round.date);
  const title = roundTitle(round);
  const unknown = title === "Round details unknown";
  return (
    <li className="py-3 text-sm">
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className={unknown ? "text-muted italic" : "font-medium"}>{title}</span>
        {date && <span className="text-muted">{date}</span>}
        {round.amount_text && <span>{round.amount_text}</span>}
      </p>
      {round.investors.length > 0 && (
        <p className="mt-1 text-muted">
          {round.investors.map((ri, i) => (
            <span key={ri.investor.id}>
              {i > 0 && ", "}
              <span className={ri.investor.id === investorId ? "font-medium text-foreground" : ""}>
                {displayName(ri.investor.name)}
              </span>
              {ri.is_lead && " (lead)"}
            </span>
          ))}
        </p>
      )}
      <div className="mt-1.5">
        <SourceBadges sources={round.sources} />
      </div>
    </li>
  );
}

/**
 * Backers Cala links to a company without any round details (A7) used to be one "Round details
 * unknown" row each; they read as one fact, so they get one row.
 */
function UnknownRounds({ rounds, investorId }: { rounds: Round[]; investorId: string }) {
  if (rounds.length === 0) return null;
  const seen = new Set<string>();
  const investors = rounds
    .flatMap((r) => r.investors)
    .filter((ri) => (seen.has(ri.investor.id) ? false : (seen.add(ri.investor.id), true)));
  const sources: Source[] = rounds.flatMap((r) => r.sources);
  return (
    <li className="py-3 text-sm">
      <p className="text-muted italic">
        {rounds.length === 1 ? "A round" : `${rounds.length} rounds`} with no label, date or amount in Cala
      </p>
      {investors.length > 0 && (
        <p className="mt-1 text-muted">
          {investors.map((ri, i) => (
            <span key={ri.investor.id}>
              {i > 0 && ", "}
              <span className={ri.investor.id === investorId ? "font-medium text-foreground" : ""}>
                {displayName(ri.investor.name)}
              </span>
            </span>
          ))}
        </p>
      )}
      <div className="mt-1.5">
        <SourceBadges sources={sources} max={2} />
      </div>
    </li>
  );
}
