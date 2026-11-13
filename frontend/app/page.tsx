import { HomeForm } from "@/components/HomeForm";

export default function Home() {
  return (
    <section>
      <h1 className="max-w-xl text-3xl font-semibold tracking-tight">
        Who&apos;s a fit, and who has a conflict.
      </h1>
      <p className="mt-3 max-w-xl text-muted">
        Pitchlist walks Cala&apos;s graph from a company to its competitors, their rounds and the
        investors behind them, and shows a source for every claim.
      </p>
      <HomeForm />
    </section>
  );
}
