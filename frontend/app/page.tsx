import Link from "next/link";

import { HomeForm } from "@/components/HomeForm";
import { founderPath } from "@/lib/routes";

// Sensofusion's live report: Skyfall Ventures backed its competitor Stendr (sources on the report).
const SENSOFUSION = "202e9283-6455-486f-8868-03c7e0d0cf29";

export default function Home() {
  return (
    <section className="grid gap-x-16 gap-y-14 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div>
        <h1 className="display max-w-4xl text-5xl sm:text-6xl xl:text-8xl">
          Know who to skip <em>before</em> Slush.
        </h1>
        <p className="mt-8 max-w-xl text-lg leading-snug text-muted">
          Who&apos;s a fit, and who has a conflict, from either side of the table. PitchSwitch walks
          Cala&apos;s graph from a company to its competitors, their rounds and the investors behind
          them, and shows a source for every claim.
        </p>
        <p className="mt-10 max-w-xl border-t border-line pt-5">
          <span className="label mr-2 inline-block rounded-[5px] bg-press px-1.5 py-1 align-middle text-background">
            Skip
          </span>
          Skyfall Ventures, for Sensofusion: it backed their competitor Stendr.{" "}
          <Link href={founderPath(SENSOFUSION)} className="text-muted underline underline-offset-4 hover:text-foreground">
            See the sources
          </Link>
        </p>
      </div>
      <HomeForm />
    </section>
  );
}
