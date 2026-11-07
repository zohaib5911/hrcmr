import { createApiClient, serverApiBaseUrl } from "@/lib/api/client";

/** An API client for pages anyone can open: no session cookie is sent. */
export function publicCareersClient() {
  return createApiClient({ baseUrl: serverApiBaseUrl(), readCookies: () => "" });
}
