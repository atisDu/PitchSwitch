"use client";

// Investor brief (C10): one page on one investor for one company, every
// sentence citing [n] into the numbered source list below it. Printable.

import Link from "next/link";
import { Fragment, useEffect, useState, type ReactNode } from "react";

import { SlowNotice } from "@/components/SlowNotice";
import { SourceBadge } from "@/components/SourceBadge";
import { ApiError, getBrief } from "@/lib/api";
import { parseMarkdown, type Block, type Inline } from "@/lib/markdown";
import { checkPath, founderPath } from "@/lib/routes";
import { safeUrl } from "@/lib/sources";
import type { Brief, Source } from "@/lib/types";

type Load =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
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
      <title>{`${title} · Brief · Pitchlist`}</title>
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

      {body.length === 0 ? (
        <p className="mt-10 text-muted">
          Cala has no facts we could cite for this pair, so there is nothing to brief yet.
        </p>
      ) : (
        <div className="mt-10 space-y-5 text-lg leading-relaxed">
          {body.map((b, i) => (
            <BlockView key={i} block={b} citations={brief.citations} />
          ))}
        </div>
      )}

      <section className="mt-16 border-t border-line pt-8" aria-labelledby="sources-heading">
        <h2 id="sources-heading" className="label">
          Sources · {brief.citations.length}
        </h2>
        <ol className="mt-4 space-y-3">
          {brief.citations.map((s, i) => (
            <CitationRow key={i} n={i + 1} source={s} />
          ))}
        </ol>
      </section>
    </article>
  );
}

function BlockView({ block, citations }: { block: Block; citations: Source[] }) {
  if (block.kind === "heading") {
    const cls = "label pt-6 text-muted";
    const inner = <InlineContent nodes={block.content} citations={citations} />;
    return block.level === 3 ? <h4 className={cls}>{inner}</h4> : <h3 className={cls}>{inner}</h3>;
  }
  if (block.kind === "list") {
    const Tag = block.ordered ? "ol" : "ul";
    return (
      <Tag className={`space-y-2 pl-6 ${block.ordered ? "list-decimal" : "list-disc marker:text-moss"}`}>
        {block.items.map((item, i) => (
          <li key={i}>
            <InlineContent nodes={item} citations={citations} />
          </li>
        ))}
      </Tag>
    );
  }
  return (
    <p>
      <InlineContent nodes={block.content} citations={citations} />
    </p>
  );
}

function InlineContent({ nodes, citations }: { nodes: Inline[]; citations: Source[] }): ReactNode {
  return nodes.map((node, i) => {
    switch (node.kind) {
      case "text":
        return <Fragment key={i}>{node.text}</Fragment>;
      case "bold":
        return (
          <strong key={i} className="font-semibold">
            <InlineContent nodes={node.children} citations={citations} />
          </strong>
        );
      case "italic":
        return (
          <em key={i}>
            <InlineContent nodes={node.children} citations={citations} />
          </em>
        );
      case "cite": {
        const src = citations[node.n - 1];
        if (!src) return <sup key={i} className="text-muted">[{node.n}]</sup>;
        return (
          <sup key={i} className="ml-0.5">
            <a
              href={`#cite-${node.n}`}
              title={`${src.name}${src.date ? `, ${src.date}` : ""}`}
              className="rounded-[3px] bg-echo px-1 font-sans text-[0.7em] font-medium text-foreground no-underline hover:bg-accent"
            >
              {node.n}
            </a>
          </sup>
        );
      }
    }
  });
}

function CitationRow({ n, source }: { n: number; source: Source }) {
  const href = safeUrl(source.url);
  return (
    <li id={`cite-${n}`} className="grid scroll-mt-24 grid-cols-[2rem_1fr] items-baseline gap-2 target:bg-echo">
      <span className="display text-2xl text-muted">{n}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        <SourceBadge source={source} />
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className="min-w-0 truncate text-sm underline underline-offset-4">
            {source.name}
          </a>
        ) : (
          <span className="text-sm">{source.name}</span>
        )}
      </div>
    </li>
  );
}

function plainText(nodes: Inline[]): string {
  return nodes
    .map((n) => (n.kind === "text" ? n.text : n.kind === "cite" ? "" : plainText(n.children)))
    .join("")
    .trim();
}
