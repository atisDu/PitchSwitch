import { Suspense } from "react";

import { FounderReportView } from "@/components/FounderReportView";

type Params = PageProps<"/founder/[companyId]">["params"];

export default function FounderPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={null}>
      <Report params={params} />
    </Suspense>
  );
}

async function Report({ params }: { params: Params }) {
  const { companyId } = await params;
  return <FounderReportView key={companyId} companyId={companyId} />;
}
