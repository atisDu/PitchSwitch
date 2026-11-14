import { Suspense } from "react";

import { HomeForm } from "@/components/HomeForm";

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    // One framed unit (chosen in live mode): the pitch on Press Black, the form beside it, no gutter.
    <section className="grid items-stretch overflow-hidden rounded-[5px] border border-foreground lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div className="bg-press px-6 py-10 text-background sm:px-10 sm:py-14">
        <h1 className="display max-w-4xl text-5xl sm:text-6xl xl:text-8xl">
          Know who to skip <em>before</em> Slush.
        </h1>
        <p className="mt-8 max-w-xl text-lg leading-snug text-sage">
          Who&apos;s a fit, and who has a conflict, from either side of the table. PitchSwitch walks
          Cala&apos;s graph from a company to its competitors, their rounds and the investors behind
          them, and shows a source for every claim.
        </p>
      </div>
      <div className="px-6 py-8 sm:px-10 sm:py-12">
        <Suspense fallback={<HomeForm />}>
          <Form searchParams={searchParams} />
        </Suspense>
      </div>
    </section>
  );
}

async function Form({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const { mode } = await searchParams;
  return <HomeForm initialMode={mode === "investor" ? "investor" : "founder"} />;
}
