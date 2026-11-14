// Minimal Markdown for briefs (C10): the subset core/briefs.py writes, parsed
// into plain data so React renders it as text (no HTML from the model ever
// reaches the DOM). Blocks: # / ## / ### headings, "-"/"*"/"1." lists,
// paragraphs. Inline: **bold**, *italic*, [n] citation markers.

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "bold"; children: Inline[] }
  | { kind: "italic"; children: Inline[] }
  | { kind: "cite"; n: number };

export type Block =
  | { kind: "heading"; level: 1 | 2 | 3; content: Inline[] }
  | { kind: "paragraph"; content: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] };

export function parseMarkdown(md: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (para.length) blocks.push({ kind: "paragraph", content: parseInline(para.join(" ")) });
    para = [];
    if (list) blocks.push({ kind: "list", ordered: list.ordered, items: list.items.map(parseInline) });
    list = null;
  };

  for (const raw of md.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      flush();
      const level = Math.min(h[1].length, 3) as 1 | 2 | 3;
      blocks.push({ kind: "heading", level, content: parseInline(h[2]) });
      continue;
    }
    const li = /^(?:([-*+])|(\d+)[.)])\s+(.*)$/.exec(line);
    if (li) {
      const ordered = Boolean(li[2]);
      if (para.length || (list && list.ordered !== ordered)) flush();
      list ??= { ordered, items: [] };
      list.items.push(li[3]);
      continue;
    }
    if (list) {
      // A plain line right after a list item continues that item.
      list.items[list.items.length - 1] += ` ${line}`;
      continue;
    }
    para.push(line);
  }
  flush();
  return blocks;
}

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  const re = /\*\*(.+?)\*\*|\*(?!\s)(.+?)\*|\[(\d{1,3})\]/g;
  let last = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > last) out.push({ kind: "text", text: text.slice(last, m.index) });
    if (m[1] !== undefined) out.push({ kind: "bold", children: parseInline(m[1]) });
    else if (m[2] !== undefined) out.push({ kind: "italic", children: parseInline(m[2]) });
    else out.push({ kind: "cite", n: Number(m[3]) });
    last = re.lastIndex;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

/** Citation numbers used anywhere in the document, in order of first use. */
export function citedNumbers(blocks: Block[]): number[] {
  const seen = new Set<number>();
  const walk = (xs: Inline[]) => {
    for (const x of xs) {
      if (x.kind === "cite") seen.add(x.n);
      else if (x.kind === "bold" || x.kind === "italic") walk(x.children);
    }
  };
  for (const b of blocks) {
    if (b.kind === "list") b.items.forEach(walk);
    else walk(b.content);
  }
  return [...seen];
}
