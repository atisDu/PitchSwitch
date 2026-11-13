"use client";

// Competitor chips (C5): one chip per competitor, the reason in a tooltip
// (hover, keyboard focus or tap), and a × to remove a wrong match.

import { useState } from "react";

import { SourceBadges } from "@/components/SourceBadge";
import type { Competitor } from "@/lib/types";

export function CompetitorChips({
  competitors,
  removed,
  onRemove,
  onRestore,
  disabled = false,
}: {
  competitors: Competitor[];
  removed: ReadonlySet<string>;
  onRemove: (id: string) => void;
  onRestore: (id: string) => void;
  disabled?: boolean;
}) {
  const kept = competitors.filter((c) => !removed.has(c.company.id));
  const gone = competitors.filter((c) => removed.has(c.company.id));

  return (
    <div>
      <ul className="relative flex flex-wrap gap-2">
        {kept.map((c) => (
          <Chip key={c.company.id} competitor={c} onRemove={onRemove} disabled={disabled} />
        ))}
      </ul>
      {gone.length > 0 && (
        <p className="mt-4 text-sm text-muted">
          <span className="label mr-2">Removed</span>
          {gone.map((c, i) => (
            <span key={c.company.id}>
              {i > 0 && ", "}
              <s>{c.company.name}</s>{" "}
              <button
                type="button"
                disabled={disabled}
                onClick={() => onRestore(c.company.id)}
                className="text-foreground underline underline-offset-4 disabled:opacity-40"
              >
                restore
              </button>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

function Chip({
  competitor,
  onRemove,
  disabled,
}: {
  competitor: Competitor;
  onRemove: (id: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { company, reason } = competitor;
  const tipId = `tip-${company.id}`;
  const meta = [company.stage, company.country].filter(Boolean).join(" · ");

  return (
    <li
      className="group md:relative"
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
    >
      <span className="inline-flex items-center rounded-[5px] border border-foreground bg-background">
        <button
          type="button"
          aria-describedby={tipId}
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="py-1.5 pr-1 pl-3 text-sm font-medium"
        >
          {company.name}
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onRemove(company.id)}
          aria-label={`Remove ${company.name} — not a real competitor`}
          title="Not a competitor? Remove it"
          className="px-2 py-1.5 text-muted hover:text-foreground disabled:opacity-40"
        >
          ×
        </button>
      </span>
      <div
        id={tipId}
        role="tooltip"
        className={`absolute top-full right-0 left-0 z-20 mt-2 border md:right-auto md:w-72 border-foreground bg-background p-4 text-left ${
          open ? "block" : "hidden group-focus-within:block group-hover:block"
        }`}
      >
        {meta && <p className="label text-muted">{meta}</p>}
        <p className="mt-2 text-sm leading-snug">{reason}</p>
        <p className="label mt-3 text-muted">Why a competitor: AI judgement</p>
        {company.description && (
          <p className="mt-3 line-clamp-4 border-t border-line pt-3 text-sm leading-snug text-muted">
            {company.description}
          </p>
        )}
        <div className="mt-3">
          <SourceBadges sources={company.sources} />
        </div>
      </div>
    </li>
  );
}
