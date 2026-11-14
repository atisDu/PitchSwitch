"use client";

// Questions inside a brief's card (brief page, Slush prep cards): a "Deeper analysis" button that
// sends one fixed prompt, and a question box. Answers stream from /api/chat into the card itself,
// with their sources, instead of the side panel the report pages use.

import { useId, useState } from "react";

import { TurnView, useChat } from "@/components/ChatPanel";

/** The fixed prompt behind "Deeper analysis" (lib/sample.ts answers it on the sample). */
export const deeperPrompt = (investor: string, company: string) =>
  `Deeper analysis: should ${company} pitch ${investor}? Answer in three short parts, each under a markdown ## heading. ` +
  `"Strong points": the facts that make ${investor} a good fit for ${company}, such as rounds it led or joined in this space, ` +
  `the stages it backs, how recently it invested, its region and investors it shares with ${company}. ` +
  `"Weak points": the facts that count against it, such as a conflict with a direct competitor, few or old deals in this space, ` +
  `a different stage or round size, or facts Cala doesn't have. ` +
  `"How to approach them": one or two sentences. Use a bullet per point, cite every fact, and say plainly what is unknown.`;

export function BriefAsk({
  companyId,
  investorId,
  investorName,
  companyName,
  suggestions,
}: {
  companyId: string;
  investorId: string;
  investorName: string;
  companyName: string;
  suggestions: string[];
}) {
  const { turns, busy, ask, stop } = useChat({ companyId, investorId });
  const [asking, setAsking] = useState(false);
  const [input, setInput] = useState("");
  const id = useId();
  const deeperDone = turns.some((t) => t.question === "Deeper analysis");

  function submit(q: string) {
    if (!q.trim() || busy) return;
    setInput("");
    void ask(q);
  }

  return (
    <div className="rounded-xl bg-surface p-4 print:hidden">
      <p className="text-sm">Go deeper on {investorName}: strong and weak points, with sources.</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {!deeperDone && (
          <button
            type="button"
            className="btn-primary"
            disabled={busy}
            onClick={() => void ask(deeperPrompt(investorName, companyName), "Deeper analysis")}
          >
            Deeper analysis
          </button>
        )}
        <button
          type="button"
          className="btn-ghost h-control-lg bg-white text-[15px]"
          aria-expanded={asking}
          aria-controls={`${id}-form`}
          onClick={() => setAsking((v) => !v)}
        >
          {asking ? "Hide the question box" : "Ask a question"}
        </button>
      </div>

      {turns.length > 0 && (
        <ol className="mt-4 space-y-6 rounded-lg bg-white p-4 md:p-5" aria-live="polite">
          {turns.map((t) => (
            <li key={t.id}>
              <TurnView turn={t} prefix={`${id}-ask`} />
            </li>
          ))}
        </ol>
      )}

      {asking && (
        <form
          id={`${id}-form`}
          className="mt-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <ul className="mb-3 flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <li key={s}>
                <button
                  type="button"
                  onClick={() => setInput(s)}
                  className="rounded-full border border-line bg-white px-3 py-1.5 text-left text-sm hover:border-control"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
          <label htmlFor={`${id}-input`} className="sr-only">
            Your question about {investorName}
          </label>
          <div className="flex items-end gap-2">
            <textarea
              id={`${id}-input`}
              autoFocus
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(input);
                }
              }}
              placeholder="e.g. Who led their last round?"
              className="min-w-0 flex-1 resize-none rounded-lg border border-control bg-white p-2.5 outline-none placeholder:text-muted focus:border-accent"
            />
            {busy ? (
              <button type="button" className="btn-ghost h-11 bg-white" onClick={stop}>
                Stop
              </button>
            ) : (
              <button type="submit" className="btn-primary" disabled={!input.trim()}>
                Ask
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
}
