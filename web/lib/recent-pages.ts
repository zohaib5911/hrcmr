/**
 * The pages a person opened lately, for the command palette (plan 8.19: stored in localStorage as
 * `brand.recentPages`, at most 8). Storage is not trusted: anything read back that is not a known
 * page of the app is dropped, so an edited value cannot put a strange link into the palette.
 */

export const RECENT_PAGES_KEY = "brand.recentPages";
export const MAX_RECENT = 8;

/** The list with `href` at the front, no repeats, at most eight long. */
export function pushRecent(list: readonly string[], href: string): string[] {
  return [href, ...list.filter((existing) => existing !== href)].slice(0, MAX_RECENT);
}

export function serialiseRecent(list: readonly string[]): string {
  return JSON.stringify(list);
}

/** The stored list, keeping only addresses in `known`. Anything unreadable is an empty list. */
export function parseRecent(raw: string | null, known: readonly string[]): string[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    const kept: string[] = [];
    for (const entry of value) {
      if (typeof entry === "string" && known.includes(entry) && !kept.includes(entry))
        kept.push(entry);
    }
    return kept.slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}
