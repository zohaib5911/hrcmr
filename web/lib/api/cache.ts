/**
 * A small stale-while-revalidate cache for GET answers (O6.1.6). A list page shows the last answer it
 * had at once and refreshes it in the background, so going back to a list never shows the skeleton
 * again. A row's detail can be fetched ahead, on hover or focus, so it opens filled in.
 *
 * It lives in this tab's memory only, holds at most `MAX_ANSWERS`, and is emptied on sign-out and on
 * a company switch: one company's or one person's data is never shown to another.
 */
import type { Outcome } from "@/lib/auth/request";

export const MAX_ANSWERS = 100;

const answers = new Map<string, unknown>();

/** The key for a GET: its path and, if any, its query in a stable order. */
export function cacheKey(path: string, query?: Record<string, unknown>): string {
  if (!query) return path;
  const sorted = Object.keys(query)
    .sort()
    .map((name) => [name, query[name]]);
  return `${path}?${JSON.stringify(sorted)}`;
}

/** The last answer for this key, if this tab has one. */
export function cached<T>(key: string): T | undefined {
  return answers.get(key) as T | undefined;
}

/** Keep an answer; the oldest one goes when the cache is full. */
export function remember(key: string, value: unknown): void {
  answers.delete(key);
  answers.set(key, value);
  if (answers.size > MAX_ANSWERS) {
    const oldest = answers.keys().next().value;
    if (oldest !== undefined) answers.delete(oldest);
  }
}

/** Fetch ahead (a row the person is about to open). Does nothing if the answer is already here. */
export async function prefetch<T>(key: string, load: () => Promise<Outcome<T>>): Promise<void> {
  if (answers.has(key)) return;
  const outcome = await load();
  if (outcome.ok) remember(key, outcome.data);
}

/** Forget everything: on sign-out and on a company switch. */
export function clearApiCache(): void {
  answers.clear();
}
