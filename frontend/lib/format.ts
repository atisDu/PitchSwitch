// Small display helpers shared by the report screens.

/** "AEROSPACE_AND_DEFENSE" → "Aerospace and defense" */
export function prettyEnum(value: string): string {
  const words = value.toLowerCase().split(/[_\s]+/).filter(Boolean);
  if (words.length === 0) return value;
  const text = words.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Remaining competitor IDs after the user removed some, in report order. */
export function keptCompetitorIds(competitorIds: string[], removed: ReadonlySet<string>): string[] {
  return competitorIds.filter((id) => !removed.has(id));
}
