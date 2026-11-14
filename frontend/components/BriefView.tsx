"use client";

// Investor brief (C10): one page on one investor for one company, every
// sentence citing [n] into the numbered source list below it. Printable.

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";
import { BriefBody, InlineContent } from "@/components/CitedText";
import { SlowNotice } from "@/components/SlowNotice";
import { describeError } from "@/lib/errors";
import { getBrief } from "@/lib/api";
import { parseMarkdown, type Inline } from "@/lib/markdown";
import { checkPath, founderPath } from "@/lib/routes";
import type { Brief } from "@/lib/types";

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
        <p className="label text-muted">Investor brief</p>
        <div className="mt-4 h-16 w-2/3 max-w-xl animate-pulse bg-surface" />
        <p className="mt-8 max-w-xl text-muted">
          Gathering this investor&apos;s rounds, portfolio and sourced answers from Cala, then
          writing one page where every sentence cites its source.
        </p>
        <SlowNotice />
      </div>
    );
  }
  if (load.status === "error") {
    return (
      <div className="max-w-xl">
        <p className="label text-muted">Investor brief</p>
        <h1 className="display mt-4 text-5xl">
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
          <Link href={founderPath(companyId)} className="btn-ghost h-[47px]">
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
      <ChatPanel
        companyId={companyId}
        investorId={investorId}
        scope={title}
        suggestions={[
          "What else has this investor led in my space?",
          "Did they back any of my competitors?",
          "Should I pitch them, and why?",
        ]}
      />
      <div className="flex flex-wrap items-center justify-between gap-4 print:hidden">
        <p className="label text-muted">Investor brief · every sentence cites its source</p>
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
      <h1 className="display mt-4 text-5xl break-words sm:text-6xl md:text-7xl">
        {titleBlock ? <InlineContent nodes={titleBlock.content} citations={brief.citations} /> : title}
      </h1>

      <BriefBody blocks={body} citations={brief.citations} anchor="cite" />
    </article>
  );
}

function plainText(nodes: Inline[]): string {
  return nodes
    .map((n) => (n.kind === "text" ? n.text : n.kind === "cite" ? "" : plainText(n.children)))
    .join("")
    .trim();
}
