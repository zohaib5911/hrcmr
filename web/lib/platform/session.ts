/**
 * Starting a platform session from the admin host (T17.1; owner answer 5, 2026-11-08).
 *
 * A platform admin's pages need the platform cookie, which only POST /auth/platform-session sets,
 * after MFA. The start is a route handler (app/(admin)/platform/session), because a server component
 * cannot set a cookie. It forwards the API's Set-Cookie to the browser. Every redirect uses the PUBLIC
 * admin path (`/session`, `/rules`), never `/platform/...`, which the proxy refuses from a browser.
 */

/** The platform cookie the API sets (PLATFORM_SESSION_COOKIE_NAME, default in app/core/config.py). */
export const PLATFORM_COOKIE = "brand_platform_session";

const INTERNAL_PREFIX = "/platform";

/** `/platform/rules` -> `/rules`; `/platform` -> `/`. Other paths pass through unchanged. */
export function toPublicPath(internal: string): string {
  if (internal === INTERNAL_PREFIX || internal === `${INTERNAL_PREFIX}/`) return "/";
  if (internal.startsWith(`${INTERNAL_PREFIX}/`)) return internal.slice(INTERNAL_PREFIX.length);
  return internal;
}

/**
 * A `next` value that is safe to redirect to: a path on this admin host, never another site, never
 * the internal segment, and nothing with a control character or a backslash. Anything else is `/`.
 */
export function safeNextPath(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/";
  if (/[\\\u0000-\u001f\u007f]/.test(raw)) return "/";
  if (raw === INTERNAL_PREFIX || raw.startsWith(`${INTERNAL_PREFIX}/`)) return "/";
  return raw;
}

export type StartOutcome = { ok: true; setCookies: string[] } | { ok: false; code: string };

/**
 * Ask the API to start the session for the person whose cookies are in `cookieHeader`. A 201 gives
 * the Set-Cookie headers to forward; a refusal gives the API's error code, for the refusal page.
 */
export async function startPlatformSession(options: {
  apiBase: string;
  cookieHeader: string;
  csrfToken?: string;
  fetchImpl?: typeof fetch;
}): Promise<StartOutcome> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const headers: Record<string, string> = {
    accept: "application/json",
    cookie: options.cookieHeader,
  };
  if (options.csrfToken) headers["X-CSRF-Token"] = options.csrfToken;
  try {
    const response = await fetchImpl(`${options.apiBase}/auth/platform-session`, {
      method: "POST",
      headers,
      cache: "no-store",
    });
    if (response.status === 201) {
      return { ok: true, setCookies: response.headers.getSetCookie() };
    }
    return { ok: false, code: await errorCode(response) };
  } catch {
    return { ok: false, code: "UNREACHABLE" };
  }
}

async function errorCode(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    const code = (body as { error?: { code?: unknown } } | null)?.error?.code;
    return typeof code === "string" ? code : "UNKNOWN";
  } catch {
    return "UNKNOWN";
  }
}

/** What the person is told when the session does not start. Plain words; no internal detail. */
export function refusalMessage(code: string): string {
  switch (code) {
    case "MFA_ENROLMENT_REQUIRED":
      return "Platform admins need two-step verification. Set it up in your account security settings, then open the admin site again.";
    case "MFA_REQUIRED":
      return "Enter the code from your authenticator app to continue, then open the admin site again.";
    case "EMAIL_NOT_VERIFIED":
      return "Confirm your email address first, then open the admin site again.";
    case "FORBIDDEN":
      return "This account is not a platform admin.";
    case "UNAUTHENTICATED":
      return "Sign in first, then open the admin site again.";
    case "UNREACHABLE":
      return "We could not reach the server. Try again in a moment.";
    default:
      return "We could not open a platform session. Try again, or ask an owner.";
  }
}

/** Whether a request carries the platform cookie. */
export function hasPlatformCookie(names: Iterable<string>): boolean {
  for (const name of names) if (name === PLATFORM_COOKIE) return true;
  return false;
}
