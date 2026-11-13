import { Suspense } from "react";

// Placeholder: C5/C6 build the founder report here.
export default function FounderPage({ params }: PageProps<"/founder/[companyId]">) {
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <Placeholder params={params} />
    </Suspense>
  );
}

async function Placeholder({ params }: { params: PageProps<"/founder/[companyId]">["params"] }) {
  const { companyId } = await params;
  return (
    <p className="text-muted">
      Founder report for <code className="font-mono">{companyId}</code> comes in task C5.
    </p>
  );
}
