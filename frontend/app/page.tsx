import { Suspense } from "react";

import { HomeForm } from "@/components/HomeForm";

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    // The landing page's hero, made to work: the headline beside the form, set in a white window on
    // the same teal-lit ground the landing page draws the app on.
    <section className="grid grid-cols-[minmax(0,1fr)] items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16">
      <div>
        <a
          href="/about"
          className="inline-flex h-8 items-center gap-2 rounded-full border border-line bg-white px-3 text-[13px] hover:border-control"
        >
          Built on Cala&apos;s company graph <span className="text-muted">See the method</span>
        </a>
        <h1 className="display mt-6 text-[44px] sm:text-6xl xl:text-[76px]">Who&apos;s a fit, and who has a conflict</h1>
        <p className="mt-6 max-w-lg text-lg text-muted">
          From either side of the table. PitchSwitch walks Cala&apos;s graph from a company to its competitors, their
          rounds and the investors behind them, and links every claim to its source.
        </p>
        <dl className="mt-10 grid max-w-lg grid-cols-2 gap-6 border-t border-line pt-5">
          <div>
            <dt className="text-sm text-muted">Founders get</dt>
            <dd className="mt-1 text-lg font-medium">A Pitch list and a Skip list</dd>
          </div>
          <div>
            <dt className="text-sm text-muted">Funds get</dt>
            <dd className="mt-1 text-lg font-medium">A portfolio conflict check</dd>
          </div>
        </dl>
      </div>
      <div className="lit-ground rounded-[20px] p-3 sm:p-8">
        <div className="window px-5 py-7 sm:px-8 sm:py-9">
          <Suspense fallback={<HomeForm />}>
            <Form searchParams={searchParams} />
          </Suspense>
        </div>
      </div>
    </section>
  );
}

async function Form({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const { mode } = await searchParams;
  return <HomeForm initialMode={mode === "investor" ? "investor" : "founder"} />;
}
