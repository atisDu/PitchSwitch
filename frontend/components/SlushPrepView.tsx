"use client";

// Slush prep (C11): paste the investors you're meeting → /api/slush-prep →
// live agent steps per investor → one cited brief card each.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { BriefBody } from "@/components/BriefView";
import { EntityPicker } from "@/components/EntityPicker";
import { ApiError, jobEvents, startSlushPrep } from "@/lib/api";
import { parseMarkdown, type Block } from "@/lib/markdown";
import { applyEvent, finish, initialPrep, MAX_NAMES, parseNames, type PrepCard, type PrepState } from "@/lib/prep";
import { briefPath, founderPath } from "@/lib/routes";
import type { EntityRef } from "@/lib/types";

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
  const [prep, setPrep] = useState<PrepState | null>(null);
  const [run, setRun] = useState<Run>({ status: "idle" });
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const parsed = parseNames(text);
  const tooMany = parsed.length > MAX_NAMES;
  const busy = run.status === "starting" || run.status === "running";
  const canStart = company !== null && parsed.length > 0 && !tooMany && !busy;

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
        message: err instanceof ApiError ? err.message : "The connection dropped.",
      });
    }
  }

  async function start() {
    if (!company || !canStart) return;
    const jobNames = parsed;
    setNames(jobNames);
    setPrep(null);
    setRun({ status: "starting" });
    try {
      const { job_id } = await startSlushPrep({ company_id: company.id, investor_names: jobNames });
      await follow(job_id, jobNames);
    } catch (err) {
      setRun({
        status: "failed",
        jobId: null,
        message: err instanceof ApiError ? err.message : "Couldn't start the prep.",
      });
    }
  }

  function stop() {
    abort.current?.abort();
    setPrep((s) => (s ? finish(s) : s));
    setRun((r) => (r.status === "running" ? { status: "finished", jobId: r.jobId } : r));
  }

  const ready = prep?.cards.filter((c) => c.status === "done").length ?? 0;
  const failed = prep?.cards.filter((c) => c.status === "error").length ?? 0;

  return (
    <div>
      <title>Slush prep · PitchSwitch</title>
      <p className="label text-muted">Slush prep</p>
      <h1 className="display mt-4 max-w-4xl text-5xl sm:text-6xl md:text-7xl">
        One sourced brief for every investor you&apos;re meeting.
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-snug text-muted">
        Paste the names from your calendar. An agent looks each one up in Cala, checks them against
        your competitors and writes a one-page brief where every sentence cites its source.
      </p>

      <div className="mt-12 grid max-w-4xl gap-10 md:grid-cols-2">
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
            className="mt-3 w-full rounded-[5px] border border-line bg-background p-3 text-base outline-none placeholder:text-muted focus:border-foreground disabled:opacity-50"
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
        </div>
      </div>

      <div className="mt-8 flex flex-wrap items-center gap-4">
        <button type="button" className="btn-primary" disabled={!canStart} onClick={() => void start()}>
          {run.status === "starting"
            ? "Starting…"
            : `Prepare ${parsed.length || ""} ${parsed.length === 1 ? "brief" : "briefs"}`.replace("  ", " ")}
        </button>
        {run.status === "running" && (
          <button type="button" className="btn-ghost h-[47px]" onClick={stop}>
            Stop
          </button>
        )}
        {company && (
          <Link href={founderPath(company.id)} className="text-sm underline underline-offset-4">
            {company.name}&apos;s founder report
          </Link>
        )}
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
              {ready} of {prep.cards.length} ready
            </h2>
            <p className="label text-muted">
              {run.status === "running"
                ? "Briefs take 20–60 s each; three run at a time"
                : failed > 0
                  ? `${failed} couldn't be briefed`
                  : "All done"}
            </p>
          </div>
          {(prep.general.length > 0 || prep.errors.length > 0) && (
            <ul className="mt-4 space-y-1 text-sm text-muted">
              {prep.general.map((g, i) => (
                <li key={`g${i}`}>{g}</li>
              ))}
              {prep.errors.map((m, i) => (
                <li key={`e${i}`} className="text-foreground">
                  {m}
                </li>
              ))}
            </ul>
          )}
          <ol className="mt-6 grid gap-4 lg:grid-cols-2">
            {prep.cards.map((c, i) => (
              <li key={c.name}>
                <Card card={c} index={i} company={company} />
              </li>
            ))}
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

function Card({ card, index, company }: { card: PrepCard; index: number; company: EntityRef | null }) {
  const blocks = card.brief ? parseMarkdown(card.brief.markdown) : [];
  const verdict = verdictOf(blocks);
  const shownName = card.investor?.name ?? card.name;
  const companyId = card.brief?.company_id ?? company?.id ?? null;

  return (
    <article
      className={`h-full border p-5 ${
        card.status === "error" ? "border-dashed border-line" : card.status === "done" ? "border-foreground" : "border-line"
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
          className={`label shrink-0 rounded-[5px] px-1.5 py-1 ${
            card.status === "done" ? "bg-accent" : card.status === "working" ? "bg-surface" : "text-muted"
          }`}
        >
          {STATUS_LABEL[card.status]}
          {card.status === "working" && <span className="ml-1 inline-block animate-pulse">…</span>}
        </span>
      </div>

      {card.status === "working" && card.steps.length > 0 && (
        <p className="mt-3 text-sm text-muted">{card.steps[card.steps.length - 1]}</p>
      )}
      {card.status === "error" && <p className="mt-3 text-sm">{card.error}</p>}

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
