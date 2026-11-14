// App URLs in one place, so screens link to each other the same way.

export const founderPath = (companyId: string) => `/founder/${encodeURIComponent(companyId)}`;

export const checkPath = (investorId: string, companyId: string) =>
  `/check/${encodeURIComponent(investorId)}/${encodeURIComponent(companyId)}`;

/** Names are display hints only (a Brief carries IDs, and live briefs have no title line). */
export const briefPath = (investorId: string, companyId: string, names?: { investor: string; company: string }) =>
  `/brief/${encodeURIComponent(investorId)}/${encodeURIComponent(companyId)}` +
  (names ? `?${new URLSearchParams({ investor: names.investor, company: names.company })}` : "");
