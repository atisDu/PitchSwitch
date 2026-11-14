// App URLs in one place, so screens link to each other the same way.

/** `raise`: the founder's optional raise in EUR (C18), kept as ?raise= */
export const founderPath = (companyId: string, raise?: number | null) =>
  `/founder/${encodeURIComponent(companyId)}` + (raise ? `?raise=${Math.round(raise)}` : "");

/** `maxCheck`: the most the investor will fund in EUR (C18), kept as ?check= */
export const checkPath = (investorId: string, companyId: string, maxCheck?: number | null) =>
  `/check/${encodeURIComponent(investorId)}/${encodeURIComponent(companyId)}` +
  (maxCheck ? `?check=${Math.round(maxCheck)}` : "");

export const prepPath = (company?: { id: string; name: string }) =>
  "/prep" + (company ? `?${new URLSearchParams({ company: company.id, companyName: company.name })}` : "");

/** Names are display hints only (a Brief carries IDs, and live briefs have no title line). */
export const briefPath = (investorId: string, companyId: string, names?: { investor: string; company: string }) =>
  `/brief/${encodeURIComponent(investorId)}/${encodeURIComponent(companyId)}` +
  (names ? `?${new URLSearchParams({ investor: names.investor, company: names.company })}` : "");
