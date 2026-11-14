import type { Metadata } from "next";
import { Instrument_Sans, Instrument_Serif } from "next/font/google";
import Link from "next/link";

import { Suspense } from "react";

import { Links, NavLinks } from "@/components/NavLinks";
import "./globals.css";

// Stand-ins for DESIGN.md's commercial faces: Instrument Sans for TWK Lausanne (a grotesk from
// the same family as the display serif, so the two read as one voice), Instrument Serif for the
// PP Mondwest display serif.
const sans = Instrument_Sans({ variable: "--font-ui", subsets: ["latin"] });
const display = Instrument_Serif({
  variable: "--font-display",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "PitchSwitch",
  description: "Who's a fit, and who has a conflict, from either side of the table. Built on Cala.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <header className="border-b border-line print:hidden">
          <div className="mx-auto flex h-16 w-full max-w-[1400px] items-center justify-between px-5 md:px-10">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Pitch<span className="border-b-2 border-accent">Switch</span>
            </Link>
            <nav className="flex items-center gap-6">
              <Suspense fallback={<Links />}>
                <NavLinks />
              </Suspense>
              <span className="label hidden text-muted md:inline">Every claim sourced from Cala</span>
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 pt-8 pb-24 md:px-10">
          {children}
        </main>
        <footer className="bg-press text-background print:hidden">
          <div className="mx-auto flex w-full max-w-[1400px] flex-wrap items-center justify-between gap-4 px-5 py-8 md:px-10">
            <span className="label">PitchSwitch</span>
            <span className="label text-sage">Data: Cala · Junction 2026</span>
          </div>
          <div className="h-3 bg-accent" />
        </footer>
      </body>
    </html>
  );
}
