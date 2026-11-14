"use client";

// Home: "I'm raising / I'm investing" toggle, then pick the entities and go.

import { useRouter } from "next/navigation";
import { useState } from "react";

import { EntityPicker } from "@/components/EntityPicker";
import { formatEuro, parseEuro } from "@/lib/money";
import { checkPath, founderPath } from "@/lib/routes";
import type { EntityRef } from "@/lib/types";

type Mode = "founder" | "investor";

const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: "founder", label: "I'm raising", hint: "Who should I pitch, and who should I skip?" },
  {
    value: "investor",
    label: "I'm investing",
    hint: "Does this startup conflict with my portfolio, and who backed its rivals?",
  },
];

export function HomeForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("founder");
  const [company, setCompany] = useState<EntityRef | null>(null);
  const [fund, setFund] = useState<EntityRef | null>(null);
  const [startup, setStartup] = useState<EntityRef | null>(null);
  // Optional amount (C18): the raise (founder) or the most the fund puts in (investor).
  const [amountText, setAmountText] = useState({ founder: "", investor: "" });
  const text = amountText[mode];
  const amount = parseEuro(text);
  const amountInvalid = text.trim() !== "" && amount === null;

  const ready = (mode === "founder" ? company !== null : fund !== null && startup !== null) && !amountInvalid;
  // Why the main button is still disabled, said under it.
  const missing =
    mode === "founder"
      ? company === null
        ? "Find your company and pick the right match first."
        : null
      : fund === null && startup === null
        ? "Find your fund and the startup first."
        : fund === null
          ? "Find your fund first."
          : startup === null
            ? "Find the startup first."
            : null;
  const blocker = missing ?? (amountInvalid ? "Fix the amount, or leave it empty." : null);

  function go() {
    if (mode === "founder" && company) router.push(founderPath(company.id, amount));
    if (mode === "investor" && fund && startup) router.push(checkPath(fund.id, startup.id, amount));
  }

  return (
    <div className="max-w-xl lg:pt-3">
      <div role="radiogroup" aria-label="Mode" className="flex gap-8 border-b border-line">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={mode === m.value}
            onClick={() => setMode(m.value)}
            className={`label -mb-px border-b-2 pb-3 transition-colors ${
              mode === m.value
                ? "border-accent text-foreground"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="mt-4 text-muted">{MODES.find((m) => m.value === mode)?.hint}</p>

      <div className="mt-10 space-y-8">
        {mode === "founder" ? (
          <EntityPicker
            key="company"
            kind="company"
            label="Your company"
            placeholder="e.g. Sensofusion"
            value={company}
            onChange={setCompany}
            examples={["Sensofusion", "Kelluu", "Stendr"]}
          />
        ) : (
          <>
            <EntityPicker
              key="fund"
              kind="investor"
              label="Your fund"
              placeholder="e.g. Tesi"
              value={fund}
              onChange={setFund}
              examples={["Tesi", "Maki.vc"]}
            />
            <EntityPicker
              key="startup"
              kind="company"
              label="The startup that pitched you"
              placeholder="e.g. NestAI"
              value={startup}
              onChange={setStartup}
              examples={["NestAI", "Stendr"]}
            />
          </>
        )}
        <div>
          <label htmlFor="home-amount" className="label">
            {mode === "founder" ? "Amount you want to raise" : "Most you will fund"}{" "}
            <span className="text-muted normal-case">(optional, EUR)</span>
          </label>
          <input
            id="home-amount"
            value={text}
            onChange={(e) => setAmountText((t) => ({ ...t, [mode]: e.target.value }))}
            placeholder={mode === "founder" ? "e.g. 3M" : "e.g. 500k"}
            inputMode="decimal"
            autoComplete="off"
            aria-invalid={amountInvalid}
            aria-describedby="home-amount-hint"
            className="mt-3 block h-11 w-48 rounded-[5px] border border-line bg-background px-3 text-base outline-none placeholder:text-muted focus:border-foreground aria-[invalid=true]:border-foreground"
          />
          <p id="home-amount-hint" className="mt-2 text-sm text-muted" aria-live="polite">
            {amountInvalid
              ? "Type an amount like 3M, 500k or 3 000 000."
              : amount !== null
                ? `${formatEuro(amount)}: compared with the round sizes in Cala.`
                : mode === "founder"
                  ? "Shows which investors join rounds of your size."
                  : "Shows whether this startup raises rounds your check fits."}
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={go}
        disabled={!ready}
        aria-describedby="home-go-hint"
        className="btn-primary mt-10"
      >
        {mode === "founder" ? "Find who to pitch" : "Check this startup"}
      </button>
      <p id="home-go-hint" className="mt-3 min-h-5 text-sm text-muted" aria-live="polite">
        {blocker}
      </p>
    </div>
  );
}
