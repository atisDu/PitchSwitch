"use client";

// Header nav with the current page marked (aria-current + the accent underline).

import Link from "next/link";
import { usePathname } from "next/navigation";

// The landing page at / is a static page outside the app (public/about.html), so it gets a plain <a>:
// a client-side <Link> would ask the app router for a route that doesn't exist.
const LINKS = [
  { href: "/", label: "How it works", external: true, wide: true }, // phones: the logo links there too
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
        // The landing's .nav__link: ink words, a 2px line drawn in from the left on hover and focus,
        // and held under the page you are on.
        const className = `relative inline-flex h-9 items-center whitespace-nowrap px-2 text-[15px] font-medium sm:px-3 pointer-coarse:h-11
          before:absolute before:inset-x-2 before:-bottom-0.5 before:h-0.5 before:origin-right before:scale-x-0 before:rounded-full
          before:bg-current before:transition-transform before:duration-200 hover:before:origin-left hover:before:scale-x-100
          focus-visible:before:origin-left focus-visible:before:scale-x-100 sm:before:inset-x-3 ${"wide" in l ? "max-sm:hidden " : ""}${
            here ? "after:absolute after:inset-x-2 after:-bottom-0.5 after:h-0.5 after:rounded-full after:bg-current sm:after:inset-x-3" : ""
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
