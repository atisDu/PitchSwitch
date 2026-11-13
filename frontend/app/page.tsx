import { HomeForm } from "@/components/HomeForm";

export default function Home() {
  return (
    <section>
      <p className="label text-muted">Fundraising, from either side of the table</p>
      <h1 className="display mt-5 max-w-4xl text-5xl sm:text-6xl md:text-8xl">
        Who&apos;s a fit, and who has a <em>conflict</em>.
      </h1>
      <p className="mt-8 max-w-xl text-lg leading-snug text-muted">
        Pitchlist walks Cala&apos;s graph from a company to its competitors, their rounds and the
        investors behind them, and shows a source for every claim.
      </p>
      <HomeForm />
    </section>
  );
}
