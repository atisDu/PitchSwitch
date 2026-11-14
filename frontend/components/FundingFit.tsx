"use client";

// Funding amount (C18, B21): the optional amount field and the fit line on cards and checks.
// Founder side: "how much you want to raise"; investor side: "the most you will fund".

import { useState } from "react";

import { SourceBadges } from "@/components/SourceBadge";
import { formatEuro, parseEuro } from "@/lib/money";
import type { FundingFit, FundingVerdict } from "@/lib/types";

export type FundingSide = "founder" | "investor";

const LABEL: Record<FundingSide, Record<FundingVerdict, string>> = {
  founder: {
    fits: "Fits your raise",
    too_small: "Raise below their range",
    too_large: "Raise above their range",
    unknown: "Round sizes unknown",
  },
  investor: {
    fits: "Fits your check",
    too_small: "Raises less than your check",
    too_large: "Your check is a small share",
    unknown: "Round sizes unknown",
  },
};

// One accent (DESIGN.md): a fit is teal-tinted, a mismatch is ink, unknown is faint.
const STYLE: Record<FundingVerdict, string> = {
  fits: "bg-echo border-moss text-foreground",
  too_small: "bg-background border-foreground text-foreground",
  too_large: "bg-background border-foreground text-foreground",
  unknown: "bg-background border-dashed border-line text-muted",
};

export function FundingFitLine({ fit, side }: { fit: FundingFit; side: FundingSide }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <span className={`label rounded-lg border px-1.5 py-1 ${STYLE[fit.verdict]}`}>{LABEL[side][fit.verdict]}</span>
      <span className={fit.verdict === "unknown" ? "text-muted" : ""}>{fit.text}</span>
      {fit.sources.length > 0 && <SourceBadges sources={fit.sources} />}
    </div>
  );
}

/**
 * The optional amount: type "3M", "€500k" or "3 000 000". `onApply(null)` clears it.
 * Shows what will be sent (€3M) before it's applied, and an error for anything that isn't an amount.
 */
export function AmountField({
  side,
  value,
  onApply,
  disabled = false,
}: {
  side: FundingSide;
  value: number | null;
  onApply: (amount: number | null) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState(value ? formatEuro(value) : "");
  const parsed = parseEuro(text);
  const invalid = text.trim() !== "" && parsed === null;
  const label = side === "founder" ? "Amount you want to raise" : "Most you will fund";
  const id = `amount-${side}`;
  const changed = (parsed ?? null) !== value;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!invalid && changed) onApply(parsed);
      }}
    >
      <label htmlFor={id} className="label">
        {label} <span className="text-muted normal-case">(optional, EUR)</span>
      </label>
      <div className="mt-2 flex items-center gap-2">
        <input
          id={id}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={side === "founder" ? "e.g. 3M" : "e.g. 500k"}
          inputMode="decimal"
          autoComplete="off"
          aria-invalid={invalid}
          aria-describedby={`${id}-hint`}
          disabled={disabled}
          className="block h-10 w-44 rounded-lg border border-control bg-white px-3 outline-none placeholder:text-muted focus:border-accent aria-[invalid=true]:border-foreground disabled:opacity-50"
        />
        <button type="submit" className="btn-ghost h-10" disabled={disabled || invalid || !changed}>
          {parsed === null && value !== null ? "Clear" : "Apply"}
        </button>
      </div>
      <p id={`${id}-hint`} className="mt-2 text-xs text-muted" aria-live="polite">
        {invalid
          ? "Type an amount like 3M, 500k or 3 000 000."
          : parsed !== null && changed
            ? `Compares ${formatEuro(parsed)} with the round sizes in Cala.`
            : side === "founder"
              ? "Compared with the sizes of the rounds each investor joins (whole rounds, not their share)."
              : "Compared with the sizes of this startup's rounds (whole rounds, not one investor's share)."}
      </p>
    </form>
  );
}
