/** Finding a page by typing part of its name (the command palette). */

export interface Searchable {
  label: string;
  group: string;
}

/** Lower case, no accents, single spaces: "  Café  Zoë " becomes "cafe zoe". */
export function normalise(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
}

function scoreWord(word: string, label: string, group: string): number {
  if (label.startsWith(word)) return 100;
  if (label.split(" ").some((part) => part.startsWith(word))) return 80;
  if (label.includes(word)) return 60;
  if (group.includes(word)) return 40;
  return 0;
}

/**
 * The items that match every word typed, best first: a name that starts with the word beats one
 * where it starts a later word, which beats one that merely contains it, which beats a match on the
 * group. Equal scores keep their original order. Nothing typed is treated as a pattern.
 */
export function rankPages<T extends Searchable>(query: string, items: readonly T[]): T[] {
  const words = normalise(query).split(" ").filter(Boolean);
  if (words.length === 0) return [...items];

  return items
    .map((item, index) => {
      const label = normalise(item.label);
      const group = normalise(item.group);
      const scores = words.map((word) => scoreWord(word, label, group));
      return {
        item,
        index,
        score: scores.every((s) => s > 0) ? scores.reduce((a, b) => a + b, 0) : 0,
      };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((entry) => entry.item);
}
