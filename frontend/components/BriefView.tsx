"use client";

// Investor brief (C10): one page on one investor for one company, every
// sentence citing [n] into the numbered source list below it. Printable.

import Link from "next/link";
import { useEffect, useState } from "react";

import { BriefScore } from "@/components/BriefScore";
import { BriefAsk } from "@/components/BriefAsk";
import { BriefBody, InlineContent } from "@/components/CitedText";
import { SlowNotice } from "@/components/SlowNotice";
import { describeError } from "@/lib/errors";
import { getBrief, resolve } from "@/lib/api";
import { displayName, investorKind } from "@/lib/format";
import { INVESTOR_WORDS } from "@/lib/match";
import { parseMarkdown, type Inline } from "@/lib/markdown";
import { checkPath, founderPath } from "@/lib/routes";
import { isSample } from "@/lib/sample";
import type { Brief, EntityRef } from "@/lib/types";

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean; detail: string | null }
  | { status: "ready"; brief: Brief };

export function BriefView({
  investorId,
  companyId,
  names,
}: {
  investorId: string;
  companyId: string;
  names: { investor: string | null; company: string | null };
}) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  // Which Cala entity the brief is about (looked up by the name from the link). Several firms
  // share names, and a brief about the wrong one reads as fact, so it's shown at the top.
  const [entity, setEntity] = useState<EntityRef | null>(null);

  useEffect(() => {
    if (!names.investor || isSample(investorId)) return;
    const ctrl = new AbortController();
    resolve(names.investor, "investor", ctrl.signal).then(
      (items) => {
        if (!ctrl.signal.aborted) setEntity(items.find((e) => e.id === investorId) ?? null);
      },
      () => {}, // the brief still stands on its own; the entity line is extra
    );
    return () => ctrl.abort();
  }, [names.investor, investorId]);

  useEffect(() => {
    const ctrl = new AbortController();
    getBrief({ investor_id: investorId, company_id: companyId }, ctrl.signal).then(
      (brief) => {
        if (!ctrl.signal.aborted) setLoad({ status: "ready", brief });
      },
      (err: unknown) => {
        if (ctrl.signal.aborted) return;
        const e = describeError(err);
        setLoad({ status: "error", message: e.message, notFound: e.notFound, detail: e.detail });
      },
    );
    return () => ctrl.abort();
  }, [investorId, companyId, attempt]);

  if (load.status === "loading") {
    return (
      <div aria-busy="true" aria-live="polite">
        <div className="h-16 w-2/3 max-w-xl animate-pulse bg-surface" />
        <p className="mt-8 max-w-xl text-muted">
          Gathering this investor&apos;s rounds and portfolio from Cala, then writing the brief.
        </p>
        <SlowNotice />
      </div>
    );
  }
  if (load.status === "error") {
    return (
      <div className="max-w-xl">
        <h1 className="display text-5xl">
          {load.notFound ? "We couldn't brief that pair." : "The brief didn't load."}
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
          <Link href={founderPath(companyId)} className="btn-ghost h-control-lg">
            Back to the report
          </Link>
        </div>
      </div>
    );
  }

  const { brief } = load;
  const blocks = parseMarkdown(brief.markdown);
  const titleBlock = blocks[0]?.kind === "heading" && blocks[0].level === 1 ? blocks[0] : null;
  const body = titleBlock ? blocks.slice(1) : blocks;
  const hinted = names.investor && names.company ? `${names.investor} × ${names.company}` : null;
  const title = titleBlock ? plainText(titleBlock.content) : (hinted ?? "Investor brief");

  return (
    <article className="max-w-3xl">
      <title>{`${title} · Brief · PitchSwitch`}</title>
      <div className="flex flex-wrap items-center justify-between gap-4 print:hidden">
        <p className="inline-flex h-8 items-center rounded-full border border-line bg-white px-3 text-[13px] text-muted">
          Investor brief
        </p>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <Link href={founderPath(companyId)} className="underline underline-offset-4">
            Founder report
          </Link>
          <Link href={checkPath(investorId, companyId)} className="underline underline-offset-4">
            Investor&apos;s view
          </Link>
          <button type="button" onClick={() => window.print()} className="btn-ghost h-9">
            Print
          </button>
        </div>
      </div>
      <h1 className="display mt-6 text-5xl break-words sm:text-6xl md:text-7xl">
        {titleBlock ? <InlineContent nodes={titleBlock.content} citations={brief.citations} /> : title}
      </h1>
      {entity && <AboutEntity entity={entity} />}

      <div className="window mt-8 p-6 md:p-10 print:border-0 print:p-0 print:shadow-none">
        <BriefAsk
          companyId={companyId}
          investorId={investorId}
          investorName={names.investor ?? title.split(" × ")[0]}
          companyName={names.company ?? title.split(" × ")[1] ?? "my company"}
          suggestions={[
            "What else has this investor led in my space?",
            "Did they back any of my competitors?",
            "Who led their last round?",
          ]}
        />
        <BriefBody
          blocks={body}
          citations={brief.citations}
          anchor="cite"
          extra={<BriefScore investorId={investorId} companyId={companyId} />}
        />
      </div>
    </article>
  );
}

function plainText(nodes: Inline[]): string {
  return nodes
    .map((n) => (n.kind === "text" ? n.text : n.kind === "cite" ? "" : plainText(n.children)))
    .join("")
    .trim();
}

/** The investor as Cala knows it, and a warning when that doesn't look like an investor at all. */
function AboutEntity({ entity }: { entity: EntityRef }) {
  const name = displayName(entity.name);
  const desc = entity.description?.trim() || null;
  const doubtful = entity.type !== "Person" && (!desc || !INVESTOR_WORDS.test(desc));
  return (
    <div className="window mt-8 p-4 text-sm md:px-5">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-medium">{name}</span>
        <span className="label text-muted">{investorKind(entity.type)} in Cala</span>
        <span className="text-muted">{desc ?? "No description in Cala."}</span>
      </p>
      {doubtful && (
        <p className="mt-3 border-l-2 border-foreground pl-3">
          {desc
            ? "Cala's description of this entity doesn't read like an investor's"
            : "Cala has no description of this entity"}
          , and several firms can share a name. If the brief below describes a different business, it
          is about another {name}.{" "}
          <Link href="/start" className="underline underline-offset-4 print:hidden">
            Not this {name}? Search again
          </Link>
        </p>
      )}
    </div>
  );
}
