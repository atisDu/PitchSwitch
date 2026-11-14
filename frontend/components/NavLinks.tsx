"use client";

// Header nav with the current page marked (aria-current + the accent underline).

import Link from "next/link";
import { usePathname } from "next/navigation";

// The landing page at / is a static page outside the app (public/about.html), so it gets a plain <a>:
// a client-side <Link> would ask the app router for a route that doesn't exist.
const LINKS = [
  { href: "/", label: "How it works", external: true },
  { href: "/prep", label: "Slush prep", external: false },
  { href: "/agents", label: "MCP", external: false },
];

export function NavLinks() {
  return <Links path={usePathname()} />;
}

/** Without a path (the Suspense fallback while the route resolves), nothing is marked. */
export function Links({ path = null }: { path?: string | null }) {
  return (
    <>
      {LINKS.map((l) => {
        const here = path === l.href;
        const className = `text-[15px] underline-offset-[6px] decoration-2 py-1 pointer-coarse:py-3 ${
          here ? "underline decoration-accent" : "text-muted hover:text-foreground"
        }`;
        return l.external ? (
          <a key={l.href} href={l.href} className={className}>
            {l.label}
          </a>
        ) : (
          <Link key={l.href} href={l.href} aria-current={here ? "page" : undefined} className={className}>
            {l.label}
          </Link>
        );
      })}
    </>
  );
}
