// App URLs in one place, so screens link to each other the same way.

export const founderPath = (companyId: string) => `/founder/${encodeURIComponent(companyId)}`;

export const checkPath = (investorId: string, companyId: string) =>
  `/check/${encodeURIComponent(investorId)}/${encodeURIComponent(companyId)}`;

export const briefPath = (investorId: string, companyId: string) =>
  `/brief/${encodeURIComponent(investorId)}/${encodeURIComponent(companyId)}`;
