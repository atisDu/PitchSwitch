"use client";

// Name → /api/resolve → the user confirms which Cala entity they mean
// (Cala has 5 "Inventure"s, so a match is never taken on name alone).

import { useEffect, useId, useRef, useState } from "react";

import { SlowNotice } from "@/components/SlowNotice";
import { describeError } from "@/lib/errors";
import { resolve } from "@/lib/api";
import { displayName, investorKind } from "@/lib/format";
import { looksLikeInvestor, splitMatches } from "@/lib/match";
import type { EntityKind, EntityRef } from "@/lib/types";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "results"; query: string; items: EntityRef[] };

export interface EntityPickerProps {
  kind: EntityKind;
  label: string;
  placeholder: string;
  value: EntityRef | null;
  onChange: (entity: EntityRef | null) => void;
  examples?: string[];
}

export function EntityPicker({ kind, label, placeholder, value, onChange, examples = [] }: EntityPickerProps) {
  const id = useId();
  const [name, setName] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });
  const [showLoose, setShowLoose] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  async function search(query: string) {
    const q = query.trim();
    if (!q) return;
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    onChange(null);
    setShowLoose(false);
    setState({ status: "loading" });
    try {
      const items = await resolve(q, kind, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setState({ status: "results", query: q, items });
      // One close match: pre-select it, still shown so the user can see what was picked.
      const { close } = splitMatches(q, items, kind === "investor");
      if (close.length === 1) onChange(close[0]);
    } catch (err) {
      if (ctrl.signal.aborted) return;
      setState({
        status: "error",
        message: describeError(err).message,
      });
    }
  }

  if (value) {
    return (
      <div>
        <p className="label">{label}</p>
        <div className="mt-3 flex items-start justify-between gap-3 border-l-2 border-accent bg-surface py-3 pr-3 pl-4">
          <EntityLine entity={value} investor={kind === "investor"} />
          <button
            type="button"
            onClick={() => onChange(null)}
            className="shrink-0 text-sm underline underline-offset-4"
          >
            Change
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void search(name);
        }}
      >
        <label htmlFor={id} className="label">
          {label}
        </label>
        <div className="mt-3 flex gap-2">
          <input
            id={id}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={placeholder}
            autoComplete="off"
            className="h-11 min-w-0 flex-1 rounded-lg border border-control bg-white px-3 text-base outline-none placeholder:text-muted focus:border-accent"
          />
          <button
            type="submit"
            disabled={!name.trim() || state.status === "loading"}
            className="btn-ghost h-11 shrink-0"
          >
            {state.status === "loading" ? "Searching…" : "Find"}
          </button>
        </div>
      </form>

      {examples.length > 0 && state.status === "idle" && (
        <p className="mt-2 text-sm text-muted">
          Try{" "}
          {examples.map((ex, i) => (
            <span key={ex}>
              {i > 0 && ", "}
              <button
                type="button"
                className="text-foreground underline underline-offset-4 pointer-coarse:py-2"
                onClick={() => {
                  setName(ex);
                  void search(ex);
                }}
              >
                {ex}
              </button>
            </span>
          ))}
        </p>
      )}

      <div aria-live="polite">
        {state.status === "loading" && (
          <>
            <p className="mt-3 text-sm text-muted">Searching Cala…</p>
            <SlowNotice />
          </>
        )}
        {state.status === "error" && (
          <p className="mt-3 border-l-2 border-foreground pl-3 text-sm">
            {state.message}{" "}
            <button type="button" className="underline" onClick={() => void search(name)}>
              Try again
            </button>
          </p>
        )}
        {state.status === "results" && (
          <Results
            query={state.query}
            items={state.items}
            kind={kind}
            showLoose={showLoose}
            onShowLoose={() => setShowLoose(true)}
            onPick={onChange}
          />
        )}
      </div>
    </div>
  );
}

function Results({
  query,
  items,
  kind,
  showLoose,
  onShowLoose,
  onPick,
}: {
  query: string;
  items: EntityRef[];
  kind: EntityKind;
  showLoose: boolean;
  onShowLoose: () => void;
  onPick: (e: EntityRef) => void;
}) {
  const noun = kind === "investor" ? "investor" : "company";
  const { close, loose } = splitMatches(query, items, kind === "investor");
  const shown = showLoose ? [...close, ...loose] : close;
  return (
    <div className="mt-3">
      {close.length === 0 ? (
        <p className="text-sm text-muted">
          No {noun} named “{query}” in Cala. Check the spelling or try the full name
          {kind === "company" ? " (e.g. with “Oy” or “AB”)" : ""}.
        </p>
      ) : (
        <p className="text-sm text-muted">
          {close.length === 1 ? "1 match" : `${close.length} matches`} for “{query}”. Which one do you
          mean?
        </p>
      )}
      {shown.length > 0 && (
        <ul className="mt-3 divide-y divide-line border-y border-line">
          {shown.map((e) => (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => onPick(e)}
                className="w-full px-1 py-3 text-left hover:bg-surface focus-visible:bg-surface"
              >
                <EntityLine entity={e} investor={kind === "investor" && looksLikeInvestor(e)} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {!showLoose && loose.length > 0 && (
        <button type="button" onClick={onShowLoose} className="mt-2 text-sm text-muted underline underline-offset-4">
          Show {loose.length} looser {loose.length === 1 ? "match" : "matches"}
          {kind === "investor" ? " (similar names, or not an investor)" : " (names that only share a common word)"}
        </button>
      )}
    </div>
  );
}

function EntityLine({ entity, investor = false }: { entity: EntityRef; investor?: boolean }) {
  // Cala types funds as Company or Organization; as an investor they read "Fund" (or "Angel").
  const kind = investor ? investorKind(entity.type) : entity.type === "Organization" ? "Organisation" : entity.type;
  return (
    <div className="min-w-0">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{displayName(entity.name)}</span>
        <span className="label text-muted">{kind}</span>
      </p>
      <p className="mt-0.5 line-clamp-2 text-sm text-muted">
        {/* "" = description not passed along (e.g. preselected from a link), so say nothing. */}
        {entity.description === "" ? null : (entity.description ?? "No description in Cala.")}
      </p>
    </div>
  );
}
