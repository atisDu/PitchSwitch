"use client";

// Investor check (C7): verdict first (conflict or not), then the market map:
// the startup and each competitor with who backed it and its round history.

import Link from "next/link";
import { useEffect, useState } from "react";

import { SlowNotice } from "@/components/SlowNotice";
import { SourceBadges } from "@/components/SourceBadge";
import { ApiError, checkInvestor } from "@/lib/api";
import { investorConflictText, marketMap, roundTitle, type MarketEntry } from "@/lib/check";
import { prettyEnum } from "@/lib/format";
import { founderPath } from "@/lib/routes";
import { formatSourceDate } from "@/lib/sources";
import type { InvestorCheck, Round } from "@/lib/types";

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
  | { status: "ready"; check: InvestorCheck };

export function InvestorCheckView({ investorId, companyId }: { investorId: string; companyId: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0); // "Try again" bumps this to refetch

  useEffect(() => {
    const ctrl = new AbortController();
    checkInvestor({ investor_id: investorId, company_id: companyId }, ctrl.signal).then(
      (check) => {
        if (!ctrl.signal.aborted) setLoad({ status: "ready", check });
      },
      (err: unknown) => {
        if (ctrl.signal.aborted) return;
        setLoad({
          status: "error",
          message: err instanceof ApiError ? err.message : "Something went wrong.",
          notFound: err instanceof ApiError && err.status === 404,
        });
      },
    );
    return () => ctrl.abort();
  }, [investorId, companyId, attempt]);

  if (load.status === "loading") {
    return (
      <div aria-busy="true" aria-live="polite">
        <p className="label text-muted">Investor check</p>
        <div className="mt-4 h-20 w-2/3 max-w-xl animate-pulse bg-surface" />
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
        <p className="label text-muted">Investor check</p>
        <h1 className="display mt-4 text-5xl">
          {load.notFound ? "We couldn't check that pair." : "The check didn't load."}
        </h1>
        <p className="mt-6 border-l-2 border-foreground pl-3">{load.message}</p>
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
          <Link href="/" className="btn-ghost h-[47px]">
            Search again
          </Link>
        </div>
      </div>
    );
  }

  const { check } = load;
  const { investor, company, conflicts } = check;
  const map = marketMap(check);
  const facts = [
    company.stage,
    company.country,
    ...company.industries.map(prettyEnum),
    company.total_funding_text && `${company.total_funding_text} raised`,
  ].filter(Boolean) as string[];

  return (
    <div>
      <title>{`${company.name} × ${investor.name} · Investor check · Pitchlist`}</title>
      <header>
        <p className="label text-muted">Investor check · as {investor.name}</p>
        <h1 className="display mt-4 text-5xl break-words sm:text-6xl md:text-8xl">{company.name}</h1>
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
            Flip: see {company.name}&apos;s founder view
          </Link>
        </div>
      </header>

      {conflicts.length > 0 ? (
        <section className="mt-16 bg-press px-6 py-10 text-background md:px-10 md:py-14" aria-labelledby="verdict">
          <p className="label text-sage">Verdict</p>
          <h2 id="verdict" className="display mt-4 text-5xl md:text-7xl">
            Conflict.
          </h2>
          <ul className="mt-8 space-y-6">
            {conflicts.map((c, i) => (
              <li key={`${c.competitor.id}-${c.kind}-${i}`}>
                <p className="max-w-3xl text-xl leading-snug">{investorConflictText(c, company.name)}</p>
                <div className="mt-2">
                  <SourceBadges sources={c.sources} max={3} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section className="mt-16 border-l-4 border-accent py-2 pl-6" aria-labelledby="verdict">
          <p className="label text-muted">Verdict</p>
          <h2 id="verdict" className="display mt-3 text-5xl md:text-6xl">
            No conflict found.
          </h2>
          <p className="mt-4 max-w-2xl text-muted">
            None of {company.name}&apos;s {check.competitors.length} competitors is in {investor.name}&apos;s
            portfolio in Cala, and no board links were found. Cala&apos;s portfolio data can be
            incomplete, so check anything that looks off.
          </p>
        </section>
      )}

      <section className="mt-20" aria-labelledby="map-heading">
        <p className="label text-muted">Market map · {check.competitors.length} competitors</p>
        <h2 id="map-heading" className="display mt-3 text-5xl md:text-6xl">
          Who backed the rivals
        </h2>
        <p className="mt-4 max-w-2xl text-muted">
          {company.name} and its competitors, with every investor Cala links to them and their
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
    <article className="grid gap-x-10 gap-y-4 border-t border-line py-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div>
        <p className="label text-muted">{isStartup ? "The startup" : competitor ? "Competitor" : "Other"}</p>
        <h3 className="mt-2 text-2xl font-medium tracking-tight">{company.name}</h3>
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
          <p className="mt-2 text-sm text-muted">No investors in Cala.</p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {backers.map((b) => {
              const you = b.investor.id === investorId;
              return (
                <li
                  key={b.investor.id}
                  className={`rounded-[5px] border px-2 py-1 text-sm ${
                    you ? "border-foreground bg-accent font-medium" : "border-line"
                  }`}
                >
                  {b.investor.name}
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
            {rounds.map((r) => (
              <RoundRow key={r.id} round={r} investorId={investorId} />
            ))}
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
                {ri.investor.name}
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
