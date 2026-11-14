import { Suspense } from "react";

import { BriefView } from "@/components/BriefView";

type Props = PageProps<"/brief/[investorId]/[companyId]">;

export default function BriefPage({ params, searchParams }: Props) {
  return (
    <Suspense fallback={null}>
      <Brief params={params} searchParams={searchParams} />
    </Suspense>
  );
}

async function Brief({ params, searchParams }: Pick<Props, "params" | "searchParams">) {
  const { investorId, companyId } = await params;
  const q = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" && v.trim() ? v.trim() : null);
  return (
    <BriefView
      key={`${investorId}/${companyId}`}
      investorId={investorId}
      companyId={companyId}
      names={{ investor: one(q.investor), company: one(q.company) }}
    />
  );
}
