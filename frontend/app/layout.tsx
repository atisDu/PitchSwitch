import type { Metadata } from "next";
import { DM_Mono, Instrument_Sans } from "next/font/google";
import Link from "next/link";

import { Suspense } from "react";

import { Links, NavLinks } from "@/components/NavLinks";
import "./globals.css";

// The landing page (public/about.html, served at /) is outside the app router, so links to / are
// plain <a>s, not <Link>s. Its faces: Instrument Sans for everything, DM Mono for sources.
const sans = Instrument_Sans({ variable: "--font-ui", subsets: ["latin"], axes: ["wdth"] });
const mono = DM_Mono({ variable: "--font-code", subsets: ["latin"], weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "PitchSwitch",
  description: "Who's a fit, and who has a conflict, from either side of the table. Built on Cala.",
};

/** The landing page's arc mark, drawn inline so the app needs none of the static kit's CSS. */
function Mark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={`h-[22px] w-[22px] fill-accent ${className}`}>
      <path d="M2.5 21.5V12a9.5 9.5 0 0 1 19 0v9.5h-6V12a3.5 3.5 0 0 0-7 0v9.5z" />
    </svg>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        {/* The landing page's bar (nav--centre): logo left, words centred, the one button right. */}
        <header className="sticky top-0 z-20 h-(--nav) border-b border-line bg-background print:hidden">
          <div className="wrap flex h-full items-center justify-between gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
            <a
              href="/"
              className="inline-flex flex-none items-center gap-2 justify-self-start text-xl leading-none font-medium tracking-[-0.02em] sm:text-[22px]"
            >
              <Mark />
              PitchSwitch
            </a>
            <nav className="flex items-center gap-1 self-stretch" aria-label="Main">
              <Suspense fallback={<Links />}>
                <NavLinks />
              </Suspense>
            </nav>
            <Link href="/start" className="btn-primary hidden justify-self-end px-6 lg:inline-flex">
              Run a check
            </Link>
          </div>
        </header>
        <main className="wrap flex-1 pt-10 pb-24 md:pt-14">{children}</main>
        <footer className="bg-press text-background print:hidden">
          <div className="wrap grid gap-8 py-14 md:grid-cols-[1fr_auto]">
            <div className="max-w-sm">
              <a href="/" className="inline-flex items-center gap-2 text-[22px] leading-none font-medium tracking-[-0.02em]">
                <Mark className="fill-moss" />
                PitchSwitch
              </a>
              <p className="mt-4 text-sage">
                Conflict checks for founders and investors on Cala&apos;s company graph, built at Junction 2026.
              </p>
            </div>
            <ul className="flex flex-wrap gap-x-8 gap-y-3 self-end text-sm">
              <li>
                <a href="/" className="text-sage underline-offset-4 hover:text-background hover:underline">
                  How it works
                </a>
              </li>
              <li>
                <Link href="/prep" className="text-sage underline-offset-4 hover:text-background hover:underline">
                  Slush prep
                </Link>
              </li>
              <li>
                <Link href="/start?mode=investor" className="text-sage underline-offset-4 hover:text-background hover:underline">
                  Check a startup
                </Link>
              </li>
              <li>
                <Link href="/agents" className="text-sage underline-offset-4 hover:text-background hover:underline">
                  MCP server
                </Link>
              </li>
            </ul>
            <p className="border-t border-slate pt-6 text-sm text-sage md:col-span-2">© 2026 PitchSwitch · Data from Cala</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
