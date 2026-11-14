import { Suspense } from "react";

import { InvestorCheckView } from "@/components/InvestorCheckView";

type Props = PageProps<"/check/[investorId]/[companyId]">;

export default function CheckPage({ params, searchParams }: Props) {
  return (
    <Suspense fallback={null}>
      <Check params={params} searchParams={searchParams} />
    </Suspense>
  );
}

// ?check=500000 carries the most the investor will fund (C18).
async function Check({ params, searchParams }: Pick<Props, "params" | "searchParams">) {
  const { investorId, companyId } = await params;
  const q = await searchParams;
  const check = typeof q.check === "string" ? Number(q.check) : NaN;
  return (
    <InvestorCheckView
      key={`${investorId}/${companyId}`}
      investorId={investorId}
      companyId={companyId}
      initialMaxCheck={Number.isFinite(check) && check > 0 ? check : null}
    />
  );
}
