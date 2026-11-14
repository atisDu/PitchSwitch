"use client";

// Slush prep (C11): paste the investors you're meeting → /api/slush-prep →
// live agent steps per investor → one cited brief card each.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { BriefBody } from "@/components/CitedText";
import { EntityPicker } from "@/components/EntityPicker";
import { describeError } from "@/lib/errors";
import { ApiError, getBrief, jobEvents, resolve, startSlushPrep } from "@/lib/api";
import { parseMarkdown, type Block } from "@/lib/markdown";
import {
  applyEvent,
  finish,
  initialPrep,
  investorSuggestions,
  MAX_NAMES,
  needsInvestorSuffix,
  parseNames,
  type PrepCard,
  type PrepState,
} from "@/lib/prep";
import { briefPath, founderPath } from "@/lib/routes";
import type { Brief, EntityRef } from "@/lib/types";

const EXAMPLE = "Maki.vc\nRainfall Ventures\nInventure\nNonexistent Capital";

type Run =
  | { status: "idle" }
  | { status: "starting" }
  | { status: "running"; jobId: string }
  | { status: "finished"; jobId: string }
  | { status: "failed"; message: string; jobId: string | null };

export function SlushPrepView({ initialCompany }: { initialCompany: EntityRef | null }) {
  const [company, setCompany] = useState<EntityRef | null>(initialCompany);
  const [text, setText] = useState("");
  const [names, setNames] = useState<string[]>([]); // the names of the current job
  // B17: also prep every Slush 2026 investor Cala's sources name (their cards arrive in the stream).
  const [allSlush, setAllSlush] = useState(false);
  const [prep, setPrep] = useState<PrepState | null>(null);
  const [run, setRun] = useState<Run>({ status: "idle" });
  // Briefs the user recovered by hand on a "Couldn't brief" card, by pasted name.
  const [recovered, setRecovered] = useState<Record<string, { investor: EntityRef; brief: Brief }>>({});
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const parsed = parseNames(text);
  const tooMany = parsed.length > MAX_NAMES;
  const busy = run.status === "starting" || run.status === "running";
  const canStart = company !== null && (parsed.length > 0 || allSlush) && !tooMany && !busy;

  // The stream replays from the start when (re)opened, so state is rebuilt from scratch.
  async function follow(jobId: string, jobNames: string[]) {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setPrep(initialPrep(jobNames));
    setRun({ status: "running", jobId });
    try {
      for await (const e of jobEvents(jobId, ctrl.signal)) {
        setPrep((s) => (s ? applyEvent(s, e) : s));
      }
      if (ctrl.signal.aborted) return;
      setPrep((s) => (s ? finish(s) : s));
      setRun({ status: "finished", jobId });
    } catch (err) {
      if (ctrl.signal.aborted) return;
      setRun({
        status: "failed",
        jobId,
        message: err instanceof ApiError && err.status === 0 ? "The connection dropped." : describeError(err).message,
      });
    }
  }

  async function start() {
    if (!company || !canStart) return;
    const jobNames = parsed;
    setNames(jobNames);
    setPrep(null);
    setRecovered({});
    setRun({ status: "starting" });
    try {
      const { job_id } = await startSlushPrep({
        company_id: company.id,
        investor_names: jobNames,
        ...(allSlush ? { all_slush_investors: true } : {}),
      });
      await follow(job_id, jobNames);
    } catch (err) {
      setRun({
        status: "failed",
        jobId: null,
        message: describeError(err).message,
      });
    }
  }

  function stop() {
    abort.current?.abort();
    setPrep((s) => (s ? finish(s) : s));
    setRun((r) => (r.status === "running" ? { status: "finished", jobId: r.jobId } : r));
  }

  // Cards as shown: a brief recovered by hand on a "Couldn't brief" card counts as ready.
  const cards: PrepCard[] = (prep?.cards ?? []).map((raw) => {
    const fix = recovered[raw.name];
    return fix ? { ...raw, status: "done", error: null, ...fix } : raw;
  });
  const ready = cards.filter((c) => c.status === "done").length;
  const failed = cards.filter((c) => c.status === "error").length;

  return (
    <div>
      <title>Slush prep · PitchSwitch</title>
      <p className="inline-flex h-8 items-center rounded-full border border-line bg-white px-3 text-[13px] text-muted">
        Slush prep
      </p>
      <h1 className="display mt-5 max-w-4xl text-5xl sm:text-6xl md:text-7xl">
        One sourced brief for every investor you&apos;re meeting.
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-snug text-muted">
        Paste the names from your calendar. An agent looks each one up in Cala, checks them against
        your competitors and writes a one-page brief where every sentence cites its source.
      </p>

      {/* The form in a white window on the landing page's lit ground, as on the home page. */}
      <div className="lit-ground mt-12 rounded-[20px] p-3 sm:p-8">
        <div className="window p-5 sm:p-8">
          <div className="grid grid-cols-[minmax(0,1fr)] gap-10 md:grid-cols-2">
            <EntityPicker
              kind="company"
              label="Your company"
              placeholder="e.g. Sensofusion"
              value={company}
              onChange={setCompany}
              examples={["Sensofusion", "Kelluu", "Stendr"]}
            />
            <div>
              <label htmlFor="names" className="label">
                Investors you&apos;re meeting
              </label>
              <textarea
                id="names"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={6}
                placeholder={"One per line, or separated by commas\ne.g. Maki.vc\nRainfall Ventures"}
                disabled={busy}
                className="mt-3 w-full rounded-lg border border-control bg-white p-3 text-base outline-none placeholder:text-muted focus:border-accent disabled:opacity-50"
              />
              <p className={`mt-1 text-sm ${tooMany ? "font-medium" : "text-muted"}`}>
                {parsed.length === 0 ? (
                  <>
                    Try{" "}
                    <button type="button" className="text-foreground underline underline-offset-4" onClick={() => setText(EXAMPLE)}>
                      four example names
                    </button>
                  </>
                ) : tooMany ? (
                  `${parsed.length} names: the limit is ${MAX_NAMES} per run.`
                ) : (
                  `${parsed.length} ${parsed.length === 1 ? "name" : "names"}`
                )}
              </p>
              <label className="mt-5 flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={allSlush}
                  onChange={(e) => setAllSlush(e.target.checked)}
                  disabled={busy}
                  className="mt-1 h-4 w-4 shrink-0 accent-[var(--accent)]"
                />
                <span>
                  <span className="font-medium">Add the Slush 2026 investors Cala knows of</span>
                  <span className="mt-0.5 block text-sm text-muted">
                    The funds Cala&apos;s sources name as attending Slush, not everyone there. Up to{" "}
                    {MAX_NAMES} briefs in all; the first run takes a few minutes.
                  </span>
                </span>
              </label>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button type="button" className="btn-primary" disabled={!canStart} onClick={() => void start()}>
              {run.status === "starting"
                ? "Starting…"
                : allSlush
                  ? parsed.length
                    ? `Prepare ${parsed.length} + Slush investors' briefs`
                    : "Prepare the Slush investors' briefs"
                  : `Prepare ${parsed.length || ""} ${parsed.length === 1 ? "brief" : "briefs"}`.replace("  ", " ")}
            </button>
            {run.status === "running" && (
              <button type="button" className="btn-ghost h-control-lg" onClick={stop}>
                Stop
              </button>
            )}
            {company && (
              <Link href={founderPath(company.id)} className="text-sm underline underline-offset-4">
                {company.name}&apos;s founder report
              </Link>
            )}
          </div>
        </div>
      </div>

      {run.status === "failed" && (
        <p className="mt-6 max-w-2xl border-l-2 border-foreground pl-3">
          {run.message}{" "}
          {run.jobId && (
            <button type="button" className="underline" onClick={() => void follow(run.jobId!, names)}>
              Reconnect
            </button>
          )}
        </p>
      )}

      {prep && (
        <section className="mt-16" aria-live="polite" aria-labelledby="prep-progress">
          <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-line pb-4">
            <h2 id="prep-progress" className="display text-4xl md:text-5xl">
              {prep.cards.length === 0 && run.status === "running"
                ? "Finding the investors…"
                : `${ready} of ${prep.cards.length} ready`}
            </h2>
            <p className="label text-muted">
              {run.status === "running"
                ? "Briefs take 20–60 s each; three run at a time"
                : failed > 0
                  ? `${failed} couldn't be briefed: see the card${failed === 1 ? "" : "s"} below`
                  : "All done"}
            </p>
          </div>
          {((run.status === "running" && prep.general.length > 0) || prep.errors.length > 0) && (
            <ul className="mt-4 space-y-1 text-sm text-muted">
              {/* Progress lines only while the job runs; once done they'd read as still happening. */}
              {run.status === "running" && prep.general.map((g, i) => <li key={`g${i}`}>{g}</li>)}
              {prep.errors.map((m, i) => (
                <li key={`e${i}`} className="text-foreground">
                  {m}
                </li>
              ))}
            </ul>
          )}
          <ol className="mt-6 grid items-start gap-4 lg:grid-cols-2">
            {cards.map((c, i) => {
              const id = c.investor?.id;
              const earlier = id ? cards.slice(0, i).find((o) => o.investor?.id === id) : undefined;
              return (
                <li key={c.name}>
                  <Card
                    card={c}
                    index={i}
                    company={company}
                    sameAs={earlier?.name ?? null}
                    onRecovered={(investor, brief) => setRecovered((r) => ({ ...r, [c.name]: { investor, brief } }))}
                  />
                </li>
              );
            })}
          </ol>
        </section>
      )}
    </div>
  );
}

const STATUS_LABEL: Record<PrepCard["status"], string> = {
  waiting: "Waiting",
  working: "Working",
  done: "Brief ready",
  error: "Couldn't brief",
};

function Card({
  card,
  index,
  company,
  sameAs,
  onRecovered,
}: {
  card: PrepCard;
  index: number;
  company: EntityRef | null;
  sameAs: string | null;
  onRecovered: (investor: EntityRef, brief: Brief) => void;
}) {
  const blocks = card.brief ? parseMarkdown(card.brief.markdown) : [];
  const verdict = verdictOf(blocks);
  const shownName = card.investor?.name ?? card.name;
  const companyId = card.brief?.company_id ?? company?.id ?? null;

  return (
    <article
      className={`rounded-[14px] p-5 ${
        card.status === "error"
          ? "border border-dashed border-control"
          : card.status === "done"
            ? "window"
            : "border border-line bg-white/60"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-xl font-medium tracking-tight">{shownName}</h3>
          {card.investor && card.investor.name.toLowerCase() !== card.name.toLowerCase() && (
            <p className="text-sm text-muted">You pasted “{card.name}”</p>
          )}
          {card.investor && <p className="label mt-1 text-muted">{card.investor.type}</p>}
        </div>
        <span
          className={`label shrink-0 rounded-lg px-1.5 py-1 ${
            card.status === "done" ? "bg-accent text-white" : card.status === "working" ? "bg-surface" : "text-muted"
          }`}
        >
          {STATUS_LABEL[card.status]}
          {card.status === "working" && <span className="ml-1 inline-block animate-pulse">…</span>}
        </span>
      </div>

      {card.status === "working" && card.steps.length > 0 && (
        <p className="mt-3 text-sm text-muted">{card.steps[card.steps.length - 1]}</p>
      )}
      {sameAs && (
        <p className="mt-2 text-sm text-muted">Same investor as “{sameAs}” above.</p>
      )}
      {card.status === "error" && (
        <>
          <p className="mt-3 text-sm">{card.error}</p>
          {company && <FindInstead name={card.name} companyId={company.id} onBrief={onRecovered} />}
        </>
      )}

      {card.brief && (
        <>
          {verdict && <p className="mt-4 text-lg leading-snug">{verdict}</p>}
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            {companyId && (
              <Link
                href={briefPath(card.brief.investor_id, companyId, {
                  investor: shownName,
                  company: company?.name ?? "",
                })}
                className="underline underline-offset-4"
              >
                Open the brief
              </Link>
            )}
            <span className="text-muted">{card.brief.citations.length} sources</span>
          </div>
          <details className="group mt-3">
            <summary className="label cursor-pointer list-none text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
              <span className="group-open:hidden">+ Read it here</span>
              <span className="hidden group-open:inline">− Hide</span>
            </summary>
            <div className="text-base [&_.text-lg]:text-base">
              <BriefBody blocks={blocks} citations={card.brief.citations} anchor={`prep-${index}-cite`} />
            </div>
          </details>
        </>
      )}
    </article>
  );
}

type Fix =
  | { status: "searching" }
  | { status: "ready"; candidates: EntityRef[] }
  | { status: "briefing"; pick: EntityRef; candidates: EntityRef[] }
  | { status: "failed"; message: string; candidates: EntityRef[] };

/**
 * On a "Couldn't brief" card: the closest Cala matches for the pasted name ("Did you mean…"),
 * a box to try another spelling, and picking a match writes that investor's brief by ID.
 */
function FindInstead({
  name,
  companyId,
  onBrief,
}: {
  name: string;
  companyId: string;
  onBrief: (investor: EntityRef, brief: Brief) => void;
}) {
  const [query, setQuery] = useState(name);
  const [searched, setSearched] = useState(name);
  const [fix, setFix] = useState<Fix>({ status: "searching" });

  useEffect(() => {
    const ctrl = new AbortController();
    // "Lifeline" only finds the Finnish VC as "Lifeline Ventures", so search that too.
    const queries = needsInvestorSuffix(searched) ? [searched, `${searched} Ventures`] : [searched];
    Promise.all(queries.map((q) => resolve(q, "investor", ctrl.signal).catch(() => [])))
      .then((lists) => {
        if (!ctrl.signal.aborted) {
          setFix({ status: "ready", candidates: investorSuggestions(searched, lists.flat()) });
        }
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setFix({ status: "ready", candidates: [] });
      });
    return () => ctrl.abort();
  }, [searched]);

  const candidates = fix.status === "searching" ? [] : fix.candidates;

  function pick(c: EntityRef) {
    setFix({ status: "briefing", pick: c, candidates });
    getBrief({ investor_id: c.id, company_id: companyId }).then(
      (brief) => onBrief(c, brief),
      (err: unknown) =>
        setFix({
          status: "failed",
          candidates,
          message: `Couldn't write a brief for ${c.name}: ${
            describeError(err).message
          }.`,
        }),
    );
  }

  if (fix.status === "briefing") {
    return (
      <p className="mt-4 border-l-2 border-accent pl-3 text-sm" aria-live="polite">
        Writing the brief for {fix.pick.name}… this takes 20–60 s.
      </p>
    );
  }

  return (
    <div className="mt-4 border-t border-line pt-4">
      {fix.status === "searching" ? (
        <p className="text-sm text-muted">Looking for close matches in Cala…</p>
      ) : candidates.length > 0 ? (
        <>
          <p className="label text-muted">Did you mean</p>
          <ul className="mt-2 space-y-1.5">
            {candidates.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => pick(c)}
                  className="w-full rounded-lg border border-line px-3 py-2 text-left hover:border-foreground"
                >
                  <span className="text-sm font-medium">{c.name}</span>
                  <span className="label ml-2 text-muted">{c.type}</span>
                  {c.description && (
                    <span className="mt-0.5 block line-clamp-1 text-xs text-muted">{c.description}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-sm text-muted">
          No investor in Cala looks like “{searched}”. Check the spelling, or try the fund&apos;s full
          name. Individual angels often can&apos;t be found by name yet.
        </p>
      )}
      {fix.status === "failed" && <p className="mt-3 text-sm">{fix.message}</p>}
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const q = query.trim();
          if (!q || q === searched) return;
          setFix({ status: "searching" });
          setSearched(q);
        }}
      >
        <label className="sr-only" htmlFor={`fix-${name}`}>
          Try another spelling for {name}
        </label>
        <input
          id={`fix-${name}`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Try another spelling"
          className="h-9 min-w-0 flex-1 rounded-lg border border-control bg-white px-2.5 text-sm outline-none focus:border-accent"
        />
        <button type="submit" className="btn-ghost h-9" disabled={!query.trim() || query.trim() === searched}>
          Search
        </button>
      </form>
    </div>
  );
}

/** The brief's verdict as plain text: the paragraph under a "Verdict" heading, else the first paragraph. */
function verdictOf(blocks: Block[]): string | null {
  const text = (b: Block | undefined) =>
    b && b.kind === "paragraph"
      ? b.content
          .map((n) => (n.kind === "text" ? n.text : n.kind === "cite" ? "" : n.children.map((c) => (c.kind === "text" ? c.text : "")).join("")))
          .join("")
          .replace(/\s+/g, " ")
          .trim()
      : null;
  const h = blocks.findIndex((b) => b.kind === "heading" && /verdict/i.test(b.content.map((n) => (n.kind === "text" ? n.text : "")).join("")));
  if (h !== -1) {
    const t = text(blocks[h + 1]);
    if (t) return t;
  }
  return text(blocks.find((b) => b.kind === "paragraph"));
}
