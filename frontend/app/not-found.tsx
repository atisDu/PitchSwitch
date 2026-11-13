import Link from "next/link";

export default function NotFound() {
  return (
    <section className="max-w-xl">
      <p className="label text-muted">404</p>
      <h1 className="display mt-4 text-5xl md:text-7xl">Nothing on this page.</h1>
      <p className="mt-6 text-muted">The link may be old or mistyped. Start again from a company or a fund.</p>
      <Link href="/" className="btn-primary mt-8">
        Back to search
      </Link>
    </section>
  );
}
