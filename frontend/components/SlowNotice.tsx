"use client";

// Shown under a loading state once it has taken a while. Uncached Cala queries
// take 20–80 s each (notes/A.md) and a cold founder report can need hundreds of
// them (notes/B.md), so a silent spinner would look broken.

import { useEffect, useState } from "react";

const STAGES: { after: number; text: string }[] = [
  { after: 8, text: "Still working. Cached companies load in seconds; a company we haven't seen before needs fresh Cala lookups." },
  { after: 45, text: "This company isn't cached yet, so every lookup goes to Cala. The first run can take several minutes; after that it's instant." },
  { after: 300, text: "Still going: this is a big one. Keep this tab open and it will appear when ready." },
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
