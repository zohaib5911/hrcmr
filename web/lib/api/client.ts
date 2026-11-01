/**
 * The typed API client (plan.md T0.7): `openapi-fetch` over the types generated from the FastAPI
 * OpenAPI document, so a path, a parameter or a response field that does not exist in the API is a
 * compile error here.
 *
 * Calls always go to the API (api.DOMAIN), never to a Next.js route handler, and carry the session
 * cookie. State-changing requests also carry the double-submit CSRF token (plan.md 4.2).
 */
import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };
/** The error body every failing API response uses. */
export type ApiErrorBody = components["schemas"]["ErrorBody"];
export type ApiErrorEnvelope = components["schemas"]["ErrorEnvelope"];

export const CSRF_COOKIE = "csrf";
export const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function readCookie(name: string, cookies: string): string | undefined {
  for (const part of cookies.split(";")) {
    const [key, ...value] = part.trim().split("=");
    if (key === name) return decodeURIComponent(value.join("="));
  }
  return undefined;
}

/** Copies the `csrf` cookie into the `X-CSRF-Token` header on requests that change data. */
export function csrfMiddleware(readCookies: () => string): Middleware {
  return {
    onRequest({ request }) {
      if (SAFE_METHODS.has(request.method.toUpperCase())) return undefined;
      const token = readCookie(CSRF_COOKIE, readCookies());
      if (token) request.headers.set(CSRF_HEADER, token);
      return request;
    },
  };
}

export interface ApiClientOptions {
  /** Ends in `/api/v1`, for example `https://api.example.com/api/v1`. */
  baseUrl: string;
  /** Defaults to the global `fetch`. Tests and server code pass their own. */
  fetch?: typeof fetch;
  /** Where the CSRF cookie is read from. Defaults to `document.cookie` in a browser. */
  readCookies?: () => string;
  /** Sent on every request, for example the caller's session `cookie` when rendering on the server. */
  headers?: Record<string, string>;
}

export function createApiClient({
  baseUrl,
  fetch: fetchImpl,
  readCookies,
  headers,
}: ApiClientOptions) {
  const client = createClient<paths>({
    baseUrl,
    credentials: "include",
    ...(fetchImpl ? { fetch: fetchImpl } : {}),
    ...(headers ? { headers } : {}),
  });
  client.use(
    csrfMiddleware(readCookies ?? (() => (typeof document === "undefined" ? "" : document.cookie))),
  );
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;

const LOCAL_API = "http://localhost:8000/api/v1";

/**
 * The API URL a browser should call. NEXT_PUBLIC_API_URL is compiled into the bundle at build time.
 * A missing value is only tolerated in development; production must not silently call localhost.
 */
export function browserApiBaseUrl(env: Record<string, string | undefined> = process.env): string {
  const url = env.NEXT_PUBLIC_API_URL;
  if (url) return url;
  if (env.NODE_ENV === "production") throw new Error("NEXT_PUBLIC_API_URL is not set.");
  return LOCAL_API;
}

/** The API URL for server-side rendering: the private network address when there is one. */
export function serverApiBaseUrl(env: Record<string, string | undefined> = process.env): string {
  return env.API_INTERNAL_URL || browserApiBaseUrl(env);
}
