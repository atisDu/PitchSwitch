import type { Metadata } from "next";

import { Landing } from "@/components/Landing";

export const metadata: Metadata = {
  title: "PitchSwitch · Investor screening for founders and VCs",
  description:
    "Who to pitch and who to skip: PitchSwitch walks Cala's graph from your company to its competitors, their rounds and the funds behind them, with a source on every claim.",
};

export default function AboutPage() {
  return <Landing />;
}
