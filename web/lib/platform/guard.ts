import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { createApiClient, serverApiBaseUrl, type ApiClient } from "@/lib/api/client";
import { PLATFORM_COOKIE } from "@/lib/platform/session";

/** An API client for an admin page, speaking with the platform cookie; none (null) without it. */
export async function platformApi(): Promise<ApiClient | null> {
  const jar = await cookies();
  if (!jar.has(PLATFORM_COOKIE)) return null;
  return createApiClient({
    baseUrl: serverApiBaseUrl(),
    headers: { cookie: jar.toString() },
    readCookies: () => "",
  });
}

/** The start page on the admin host, coming back to `path` afterwards (a PUBLIC admin path, e.g. `/companies`). */
export function sessionStartPath(path: string): string {
  return `/session?next=${encodeURIComponent(path)}`;
}

/** True when the API refused because the platform session is missing or has run out. */
export function isSessionRefusal(status: number | undefined): boolean {
  return status === 401 || status === 403;
}

/**
 * Every admin screen's server page uses this on each API answer: a 401/403 (for example an expired
 * platform cookie) sends the browser to the start page and back, instead of showing a 404.
 * Returns the data, or `null` for any other failure so the page can show its error state.
 */
export function dataOrSessionRedirect<T>(
  result: { data?: T; response: { status: number } },
  path: string,
): T | null {
  if (isSessionRefusal(result.response.status)) redirect(sessionStartPath(path));
  return result.data ?? null;
}
