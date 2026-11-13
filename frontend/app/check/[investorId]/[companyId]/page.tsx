import { Suspense } from "react";

type Params = PageProps<"/check/[investorId]/[companyId]">["params"];

// Placeholder: C7 builds the investor check here.
export default function CheckPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <Placeholder params={params} />
    </Suspense>
  );
}

async function Placeholder({ params }: { params: Params }) {
  const { investorId, companyId } = await params;
  return (
    <p className="text-muted">
      Investor check for <code className="font-mono">{investorId}</code> ×{" "}
      <code className="font-mono">{companyId}</code> comes in task C7.
    </p>
  );
}
