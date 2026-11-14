"use client";

// Chat panel (C12): ask follow-up questions on a report, check or brief page.
// Answers stream from /api/chat, scoped to the page's company / investor; every
// sentence cites a Cala fact. The contract has no history: each question stands
// alone, so the thread is just a list of independent Q&As.

import { useEffect, useRef, useState } from "react";

import { InlineContent } from "@/components/CitedText";
import { SourceBadge } from "@/components/SourceBadge";
import { describeError } from "@/lib/errors";
import { chat } from "@/lib/api";
import { applyChatEvent, emptyAnswer, type ChatAnswer } from "@/lib/chat";
import { parseInline } from "@/lib/markdown";
import { safeUrl } from "@/lib/sources";

interface Turn {
  id: number;
  question: string;
  answer: ChatAnswer;
}

export function ChatPanel({
  companyId,
  investorId,
  scope,
  suggestions,
}: {
  companyId?: string;
  investorId?: string;
  scope: string; // e.g. "Sensofusion Oy" or "Rainfall Ventures × Sensofusion Oy"
  suggestions: string[];
}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);
  const openerRef = useRef<HTMLButtonElement | null>(null);
  const wasOpen = useRef(false);

  useEffect(() => () => abort.current?.abort(), []);
  // Block body on purpose: newer Chrome's scrollIntoView returns a value, and an expression body
  // would hand it to React as the effect's cleanup, which React then calls ("i is not a function").
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns]);
  useEffect(() => {
    if (!open) {
      // Back to the button that opened the panel, so keyboard users don't land at the top.
      if (wasOpen.current) openerRef.current?.focus();
      return;
    }
    wasOpen.current = true;
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
      if (e.key !== "Tab" || !panelRef.current) return;
      // A modal panel keeps Tab inside it.
      const items = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), summary',
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const id = nextId.current++;
    const ctrl = new AbortController();
    abort.current = ctrl;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { id, question: q, answer: emptyAnswer() }]);
    const update = (f: (a: ChatAnswer) => ChatAnswer) =>
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, answer: f(x.answer) } : x)));
    try {
      for await (const e of chat(
        { message: q, ...(companyId ? { company_id: companyId } : {}), ...(investorId ? { investor_id: investorId } : {}) },
        ctrl.signal,
      )) {
        update((a) => applyChatEvent(a, e));
      }
      update((a) => (a.done || a.error ? a : { ...a, done: true }));
    } catch (err) {
      if (!ctrl.signal.aborted) {
        update((a) => ({ ...a, error: describeError(err).message }));
      } else {
        update((a) => ({ ...a, error: a.error ?? "Stopped." }));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          ref={openerRef}
          type="button"
          onClick={() => setOpen(true)}
          className="btn-primary fixed right-5 bottom-5 z-30 print:hidden"
          aria-haspopup="dialog"
        >
          Ask about this
        </button>
      )}
      {open && (
        <aside
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label={`Ask about ${scope}`}
          className="fixed inset-0 z-40 flex flex-col border-line bg-background sm:inset-y-0 sm:right-0 sm:left-auto sm:w-[28rem] sm:border-l print:hidden"
        >
          <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <p className="label text-muted">Ask · answers cite Cala</p>
              <p className="mt-1 truncate font-medium">{scope}</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="label text-muted hover:text-foreground">
              Close
            </button>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-5">
            {turns.length === 0 ? (
              <div>
                <p className="text-muted">
                  Ask anything about {scope}. Each question is answered on its own, from Cala facts
                  only; every sentence links to its source. Pick a question to edit it before you
                  ask.
                </p>
                <ul className="mt-5 space-y-2">
                  {suggestions.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        onClick={() => {
                          setInput(s);
                          inputRef.current?.focus();
                        }}
                        className="w-full rounded-[5px] border border-line px-3 py-2 text-left text-sm hover:border-foreground"
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <ol className="space-y-8">
                {turns.map((t) => (
                  <li key={t.id}>
                    <TurnView turn={t} />
                  </li>
                ))}
              </ol>
            )}
            <div ref={endRef} />
          </div>

          <form
            className="border-t border-line p-4"
            onSubmit={(e) => {
              e.preventDefault();
              void ask(input);
            }}
          >
            <label htmlFor="chat-input" className="sr-only">
              Your question
            </label>
            <div className="flex items-end gap-2">
              <textarea
                id="chat-input"
                ref={inputRef}
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void ask(input);
                  }
                }}
                placeholder="e.g. Who led their last round?"
                className="min-w-0 flex-1 resize-none rounded-[5px] border border-line bg-background p-2.5 outline-none placeholder:text-muted focus:border-foreground"
              />
              {busy ? (
                <button type="button" className="btn-ghost h-11" onClick={() => abort.current?.abort()}>
                  Stop
                </button>
              ) : (
                <button type="submit" className="btn-ghost h-11" disabled={!input.trim()}>
                  Ask
                </button>
              )}
            </div>
          </form>
        </aside>
      )}
    </>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const { question, answer, id } = turn;
  const anchor = `chat-${id}-cite`;
  const waiting = !answer.text && !answer.done && !answer.error;
  return (
    <article>
      <p className="border-l-2 border-accent pl-3 font-medium">{question}</p>
      {waiting && (
        <p className="mt-3 text-sm text-muted" aria-live="polite">
          {answer.steps.at(-1) ?? "Thinking"}
          <span className="ml-1 inline-block animate-pulse">…</span> <Elapsed />
        </p>
      )}
      {answer.text && (
        <p className="mt-3 leading-relaxed">
          <InlineContent nodes={parseInline(answer.text)} citations={answer.citations} anchor={anchor} />
        </p>
      )}
      {answer.done && !answer.text && !answer.error && (
        <p className="mt-3 text-muted">No sourced answer came back for this question.</p>
      )}
      {answer.error && <p className="mt-3 border-l-2 border-foreground pl-3 text-sm">{answer.error}</p>}
      {answer.citations.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {answer.citations.map((s, i) => {
            const href = safeUrl(s.url);
            return (
              <li key={i} id={`${anchor}-${i + 1}`} className="flex min-w-0 scroll-mt-4 items-center gap-2 text-xs target:bg-echo">
                <span className="w-4 shrink-0 text-right text-muted">{i + 1}</span>
                <SourceBadge source={s} />
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="min-w-0 truncate underline underline-offset-2">
                    {s.name}
                  </a>
                ) : (
                  <span className="min-w-0 truncate">{s.name}</span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </article>
  );
}

/** Seconds since this waiting line appeared: answers that need Cala's sourced search can take a minute or two. */
function Elapsed() {
  const [s, setS] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setS((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  if (s < 5) return null;
  return (
    <span className="whitespace-nowrap">
      ({s} s{s >= 30 ? "; questions that need Cala's sourced search can take a minute or two" : ""})
    </span>
  );
}
