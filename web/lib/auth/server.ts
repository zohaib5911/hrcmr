/**
 * Asking the API who is signed in, from a server component. The browser's session cookie is passed
 * along, so the answer is about the person looking at the page.
 */
import { cookies } from "next/headers";

import {
  createApiClient,
  serverApiBaseUrl,
  type ApiClient,
  type components,
} from "@/lib/api/client";

export type Me = components["schemas"]["MeResponse"];

/** The API sets this cookie (SESSION_COOKIE_NAME in the API's settings). */
export const SESSION_COOKIE = "brand_session";

/** An API client that speaks for the person looking at the page, or `null` if nobody is signed in. */
export async function serverApi(): Promise<ApiClient | null> {
  const jar = await cookies();
  if (!jar.has(SESSION_COOKIE)) return null;
  return createApiClient({
    baseUrl: serverApiBaseUrl(),
    headers: { cookie: jar.toString() },
    readCookies: () => "",
  });
}

/** The signed-in person, or `null` when nobody is signed in or the API cannot be reached. */
export async function fetchMe(): Promise<Me | null> {
  try {
    const client = await serverApi();
    if (!client) return null;
    const { data } = await client.GET("/auth/me");
    return data ?? null;
  } catch {
    return null;
  }
}
