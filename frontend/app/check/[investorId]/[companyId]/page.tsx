import { Suspense } from "react";

import { InvestorCheckView } from "@/components/InvestorCheckView";

type Params = PageProps<"/check/[investorId]/[companyId]">["params"];

export default function CheckPage({ params }: { params: Params }) {
  return (
    <Suspense fallback={null}>
      <Check params={params} />
    </Suspense>
  );
}

async function Check({ params }: { params: Params }) {
  const { investorId, companyId } = await params;
  return (
    <InvestorCheckView key={`${investorId}/${companyId}`} investorId={investorId} companyId={companyId} />
  );
}
