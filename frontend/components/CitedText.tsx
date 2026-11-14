// Cited text: brief blocks, inline [n] markers and numbered source lists.
// Its own module on purpose: BriefView renders ChatPanel and ChatPanel renders cited text, and
// importing it from BriefView made a cycle that left InlineContent undefined in the production
// bundle ("i is not a function" when a chat answer arrived).

import { Fragment, type ReactNode } from "react";

import { SourceBadge } from "@/components/SourceBadge";
import type { Block, Inline } from "@/lib/markdown";
import { safeUrl } from "@/lib/sources";
import type { Source } from "@/lib/types";

/** Brief text and its numbered sources. `anchor` keeps citation links unique when several briefs share a page. */
export function BriefBody({ blocks, citations, anchor }: { blocks: Block[]; citations: Source[]; anchor: string }) {
  return (
    <>
      {blocks.length === 0 ? (
        <p className="mt-10 text-muted">
          Cala has no facts we could cite for this pair, so there is nothing to brief yet.
        </p>
      ) : (
        <div className="mt-10 space-y-5 text-lg leading-relaxed">
          {blocks.map((b, i) => (
            <BlockView key={i} block={b} citations={citations} anchor={anchor} />
          ))}
        </div>
      )}
      <section className="mt-16 border-t border-line pt-8">
        <h2 className="label">Sources · {citations.length}</h2>
        <ol className="mt-4 space-y-3">
          {citations.map((s, i) => (
            <CitationRow key={i} n={i + 1} source={s} anchor={anchor} />
          ))}
        </ol>
      </section>
    </>
  );
}

function BlockView({ block, citations, anchor }: { block: Block; citations: Source[]; anchor: string }) {
  if (block.kind === "heading") {
    const cls = "label pt-6 text-muted";
    const inner = <InlineContent nodes={block.content} citations={citations} anchor={anchor} />;
    // Under the page's h1: markdown ## is a section (h2), ### a subsection (h3); no level is skipped.
    return block.level >= 3 ? <h3 className={cls}>{inner}</h3> : <h2 className={cls}>{inner}</h2>;
  }
  if (block.kind === "list") {
    const Tag = block.ordered ? "ol" : "ul";
    return (
      <Tag className={`space-y-2 pl-6 ${block.ordered ? "list-decimal" : "list-disc marker:text-moss"}`}>
        {block.items.map((item, i) => (
          <li key={i}>
            <InlineContent nodes={item} citations={citations} anchor={anchor} />
          </li>
        ))}
      </Tag>
    );
  }
  return (
    <p>
      <InlineContent nodes={block.content} citations={citations} anchor={anchor} />
    </p>
  );
}

/** Inline brief/chat text: bold, italic and [n] citation links into `#${anchor}-n`. */
export function InlineContent({
  nodes,
  citations,
  anchor = "cite",
}: {
  nodes: Inline[];
  citations: Source[];
  anchor?: string;
}): ReactNode {
  return nodes.map((node, i) => {
    switch (node.kind) {
      case "text":
        return <Fragment key={i}>{node.text}</Fragment>;
      case "bold":
        return (
          <strong key={i} className="font-semibold">
            <InlineContent nodes={node.children} citations={citations} anchor={anchor} />
          </strong>
        );
      case "italic":
        return (
          <em key={i}>
            <InlineContent nodes={node.children} citations={citations} anchor={anchor} />
          </em>
        );
      case "cite": {
        const src = citations[node.n - 1];
        if (!src) return <sup key={i} className="text-muted">[{node.n}]</sup>;
        return (
          <sup key={i} className="ml-0.5">
            <a
              href={`#${anchor}-${node.n}`}
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

function CitationRow({ n, source, anchor }: { n: number; source: Source; anchor: string }) {
  const href = safeUrl(source.url);
  return (
    <li id={`${anchor}-${n}`} className="grid scroll-mt-24 grid-cols-[2rem_1fr] items-baseline gap-2 target:bg-echo">
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

