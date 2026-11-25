/**
 * A small stale-while-revalidate cache for GET answers (O6.1.6). A list page shows the last answer it
 * had at once and refreshes it in the background, so going back to a list never shows the skeleton
 * again. A row's detail can be fetched ahead, on hover or focus, so it opens filled in.
 *
 * It lives in this tab's memory only, holds at most `MAX_ANSWERS`, and is emptied on sign-out and on
 * a company switch: one company's or one person's data is never shown to another.
 *
 * Each clear starts a new context (`cacheContext`). The signed-in pages are keyed by it, so a switch
 * remounts them at once: the earlier company's rows leave the screen and any answer still on its
 * way back is dropped by the unmounted component. An answer for a request started in an earlier
 * context is never kept either.
 */
import { useSyncExternalStore } from "react";

import type { Outcome } from "@/lib/auth/request";

export const MAX_ANSWERS = 100;

const answers = new Map<string, unknown>();
let context = 0;
const listeners = new Set<() => void>();

/** The current context: a new one starts on every sign-out and company switch. */
export function cacheContext(): number {
  return context;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The current context, re-rendering the caller when a new one starts. */
export function useCacheContext(): number {
  return useSyncExternalStore(subscribe, cacheContext, () => 0);
}

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

/**
 * Keep an answer; the oldest one goes when the cache is full. `from` is the context the request
 * started in: an answer from an earlier context (before a switch or sign-out) is not kept.
 */
export function remember(key: string, value: unknown, from: number = context): void {
  if (from !== context) return;
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
  const from = context;
  const outcome = await load();
  if (outcome.ok) remember(key, outcome.data, from);
}

/** Forget everything: on sign-out and on a company switch. */
export function clearApiCache(): void {
  answers.clear();
  context += 1;
  for (const listener of listeners) listener();
}
