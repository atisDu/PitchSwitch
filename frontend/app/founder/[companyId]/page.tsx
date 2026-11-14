import { Suspense } from "react";

import { FounderReportView } from "@/components/FounderReportView";

type Props = PageProps<"/founder/[companyId]">;

export default function FounderPage({ params, searchParams }: Props) {
  return (
    <Suspense fallback={null}>
      <Report params={params} searchParams={searchParams} />
    </Suspense>
  );
}

// ?raise=3000000 carries the founder's optional raise (C18).
async function Report({ params, searchParams }: Pick<Props, "params" | "searchParams">) {
  const { companyId } = await params;
  const q = await searchParams;
  const raise = typeof q.raise === "string" ? Number(q.raise) : NaN;
  return (
    <FounderReportView
      key={companyId}
      companyId={companyId}
      initialTarget={Number.isFinite(raise) && raise > 0 ? raise : null}
    />
  );
}
