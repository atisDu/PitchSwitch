// Euro amounts typed by people: "3M", "€500k", "3 000 000", "2.5m", "1,2 M", "3 million".

const SUFFIX: Record<string, number> = { k: 1e3, m: 1e6, mn: 1e6, b: 1e9, bn: 1e9 };

/** A positive amount in euros, or null when the text isn't one (empty, zero, negative, junk). */
export function parseEuro(text: string): number | null {
  const t = text
    .trim()
    .toLowerCase()
    .replace(/€|eur(o|os)?/g, "")
    .replace(/\b(millions?|mio|mill?)\b/g, "m") // "3 million", "3 mio"
    .replace(/\b(thousands?|tsd)\b/g, "k")
    .replace(/\b(billions?)\b/g, "b")
    .replace(/\s+/g, "");
  const m = /^(\d+(?:[.,]\d+)*)(k|m|mn|b|bn)?$/.exec(t);
  if (!m) return null;
  let num = m[1];
  // "1,2" / "2.5" with a suffix = decimal; "3,000,000" / "3.000.000" without = thousands separators.
  if (m[2]) {
    if (/[.,].*[.,]/.test(num)) return null; // "1.2.3k"
    num = num.replace(",", ".");
  } else if (/^\d{1,3}([.,]\d{3})+$/.test(num)) {
    num = num.replace(/[.,]/g, "");
  } else {
    num = num.replace(",", ".");
  }
  const value = Number(num) * (m[2] ? SUFFIX[m[2]] : 1);
  return Number.isFinite(value) && value > 0 ? Math.round(value) : null;
}

/** €3M, €500k, €1.2M, €2B */
export function formatEuro(value: number): string {
  const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, ""));
  if (value >= 1e9) return `€${fmt(value / 1e9)}B`;
  if (value >= 1e6) return `€${fmt(Math.round(value / 1e5) / 10)}M`;
  if (value >= 1e3) return `€${fmt(Math.round(value / 1e2) / 10)}k`;
  return `€${value}`;
}
