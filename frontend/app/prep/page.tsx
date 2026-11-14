import { Suspense } from "react";

import { SlushPrepView } from "@/components/SlushPrepView";

type Props = PageProps<"/prep">;

export default function PrepPage({ searchParams }: Props) {
  return (
    <Suspense fallback={null}>
      <Prep searchParams={searchParams} />
    </Suspense>
  );
}

// /prep?company=<id>&companyName=<name> preselects the company (link from the founder report).
async function Prep({ searchParams }: Pick<Props, "searchParams">) {
  const q = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" && v.trim() ? v.trim() : null);
  const id = one(q.company);
  const name = one(q.companyName);
  return (
    <SlushPrepView
      initialCompany={id && name ? { id, name, type: "Company", description: "" } : null}
    />
  );
}
