"use client";

// Header nav with the current page marked (aria-current + the accent underline).

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/about", label: "How it works" },
  { href: "/prep", label: "Slush prep" },
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
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={here ? "page" : undefined}
            className={`label border-b-2 py-1 pointer-coarse:py-3 ${
              here ? "border-accent" : "border-transparent hover:border-foreground"
            }`}
          >
            {l.label}
          </Link>
        );
      })}
    </>
  );
}
