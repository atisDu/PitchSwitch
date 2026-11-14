import Link from "next/link";

export default function NotFound() {
  return (
    <section className="max-w-xl">
      <p className="inline-flex h-8 items-center rounded-full border border-line bg-white px-3 text-[13px] text-muted">404</p>
      <h1 className="display mt-5 text-5xl md:text-7xl">Nothing on this page.</h1>
      <p className="mt-6 text-muted">The link may be old or mistyped. Start again from a company or a fund.</p>
      <Link href="/start" className="btn-primary mt-8">
        Back to search
      </Link>
    </section>
  );
}
