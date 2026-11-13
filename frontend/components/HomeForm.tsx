"use client";

// Home: "I'm raising / I'm investing" toggle, then pick the entities and go.

import { useRouter } from "next/navigation";
import { useState } from "react";

import { EntityPicker } from "@/components/EntityPicker";
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

  const ready = mode === "founder" ? company !== null : fund !== null && startup !== null;

  function go() {
    if (mode === "founder" && company) router.push(founderPath(company.id));
    if (mode === "investor" && fund && startup) router.push(checkPath(fund.id, startup.id));
  }

  return (
    <div className="mt-8 max-w-xl">
      <div role="radiogroup" aria-label="Mode" className="inline-flex rounded-lg border border-line p-1">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={mode === m.value}
            onClick={() => setMode(m.value)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              mode === m.value ? "bg-foreground text-background" : "text-muted hover:text-foreground"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="mt-3 text-sm text-muted">{MODES.find((m) => m.value === mode)?.hint}</p>

      <div className="mt-6 space-y-6">
        {mode === "founder" ? (
          <EntityPicker
            key="company"
            kind="company"
            label="Your company"
            placeholder="e.g. Kelluu"
            value={company}
            onChange={setCompany}
            examples={["Kelluu", "Sensofusion", "Stendr"]}
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
      </div>

      <button
        type="button"
        onClick={go}
        disabled={!ready}
        className="mt-8 h-11 rounded-lg bg-foreground px-5 font-medium text-background disabled:opacity-30"
      >
        {mode === "founder" ? "Find who to pitch" : "Check this startup"}
      </button>
    </div>
  );
}
