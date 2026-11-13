"use client";

// Name → /api/resolve → the user confirms which Cala entity they mean
// (Cala has 5 "Inventure"s, so a match is never taken on name alone).

import { useEffect, useId, useRef, useState } from "react";

import { ApiError, resolve } from "@/lib/api";
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
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  async function search(query: string) {
    const q = query.trim();
    if (!q) return;
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    onChange(null);
    setState({ status: "loading" });
    try {
      const items = await resolve(q, kind, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setState({ status: "results", query: q, items });
      // One match: pre-select it, still shown so the user can see what was picked.
      if (items.length === 1) onChange(items[0]);
    } catch (err) {
      if (ctrl.signal.aborted) return;
      setState({
        status: "error",
        message: err instanceof ApiError ? err.message : "Something went wrong.",
      });
    }
  }

  if (value) {
    return (
      <div>
        <p className="text-sm font-medium">{label}</p>
        <div className="mt-2 flex items-start justify-between gap-3 rounded-lg border border-foreground/20 bg-surface p-3">
          <EntityLine entity={value} />
          <button
            type="button"
            onClick={() => onChange(null)}
            className="shrink-0 text-sm text-muted underline-offset-2 hover:text-foreground hover:underline"
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
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <div className="mt-2 flex gap-2">
          <input
            id={id}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={placeholder}
            autoComplete="off"
            className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-background px-3 outline-none placeholder:text-muted focus:border-foreground/40"
          />
          <button
            type="submit"
            disabled={!name.trim() || state.status === "loading"}
            className="h-10 shrink-0 rounded-lg bg-foreground px-4 text-sm font-medium text-background disabled:opacity-40"
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
                className="underline underline-offset-2 hover:text-foreground"
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
        {state.status === "loading" && <p className="mt-3 text-sm text-muted">Searching Cala…</p>}
        {state.status === "error" && (
          <p className="mt-3 text-sm text-red-700 dark:text-red-400">
            {state.message}{" "}
            <button type="button" className="underline" onClick={() => void search(name)}>
              Try again
            </button>
          </p>
        )}
        {state.status === "results" && state.items.length === 0 && (
          <p className="mt-3 text-sm text-muted">
            No {kind === "investor" ? "investor" : "company"} named “{state.query}” in Cala. Check the
            spelling or try the full legal name.
          </p>
        )}
        {state.status === "results" && state.items.length > 1 && (
          <div className="mt-3">
            <p className="text-sm text-muted">
              {state.items.length} matches for “{state.query}”. Which one do you mean?
            </p>
            <ul className="mt-2 divide-y divide-line overflow-hidden rounded-lg border border-line">
              {state.items.map((e) => (
                <li key={e.id}>
                  <button
                    type="button"
                    onClick={() => onChange(e)}
                    className="w-full p-3 text-left hover:bg-surface focus-visible:bg-surface focus-visible:outline-none"
                  >
                    <EntityLine entity={e} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function EntityLine({ entity }: { entity: EntityRef }) {
  return (
    <div className="min-w-0">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{entity.name}</span>
        <span className="rounded border border-line px-1.5 text-xs text-muted">{entity.type}</span>
      </p>
      <p className="mt-0.5 line-clamp-2 text-sm text-muted">
        {entity.description ?? "No description in Cala."}
      </p>
    </div>
  );
}
