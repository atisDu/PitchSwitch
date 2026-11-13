"use client";

// Shown under a loading state once it has taken a while. Uncached Cala queries
// take 20–80 s (notes/A.md), so a silent spinner would look broken.

import { useEffect, useState } from "react";

const STAGES: { after: number; text: string }[] = [
  { after: 8, text: "Still working. Fresh Cala lookups can take up to a minute; cached ones are instant." },
  { after: 45, text: "Almost there. This company isn't cached yet, so every lookup goes to Cala." },
  { after: 90, text: "This is taking unusually long. You can wait, or go back and try again." },
];

export function SlowNotice() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const stage = [...STAGES].reverse().find((s) => seconds >= s.after);
  if (!stage) return null;
  return (
    <p className="mt-4 max-w-xl border-l-2 border-accent pl-3 text-sm" role="status">
      {stage.text} <span className="text-muted">({seconds} s)</span>
    </p>
  );
}
