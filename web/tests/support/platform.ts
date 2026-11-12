/**
 * A platform admin for a browser test (T17.1; C3.1.3). The test API makes the account a platform admin
 * (api/tests/e2e_server.py, POST /e2e/platform-admin), the account signs in with two-step verification,
 * and the platform cookie it gets is copied to the admin host in the browser.
 *
 * The browser start at /session is not used here: that call goes from the admin host to the API on
 * another origin, and the SameSite=Lax session cookie does not go with a cross-site call. In production
 * both are one site, so the start works there (components/platform/session-start.test.tsx covers it).
 *
 * Client code cannot run on the admin host in these tests: it is plain http, and the production CSP's
 * upgrade-insecure-requests turns its script and style requests into https, which the local server does
 * not answer. Pages that need JavaScript on the admin host cannot be tested here until that is solved
 * (STATUS, Issues). The server-rendered admin pages can.
 */
import { expect, type Page } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount, type Account } from "./accounts";
import { totp } from "./totp";

/** The admin host, mapped to the local web server by playwright.config.ts. */
export const ADMIN_HOST = "admin.example.test";
export const ADMIN_ORIGIN = `http://${ADMIN_HOST}:3100`;

/** The platform cookie the API sets (PLATFORM_SESSION_COOKIE_NAME). */
export const PLATFORM_COOKIE = "brand_platform_session";

/** Must match E2E_TOTP_SECRET in api/tests/e2e_server.py. */
export const PLATFORM_TOTP_SECRET = "JBSWY3DPEHPK3PXP";

/** Signs a new account in as a platform admin at `level`, with the platform cookie for the admin host. */
export async function signInPlatformAdmin(
  page: Page,
  level: "owner" | "support",
): Promise<Account> {
  // Simulate the authenticated edge only on requests to the local admin web host.
  await page.route(`${ADMIN_ORIGIN}/**`, async (route) => {
    await route.continue({
      headers: {
        ...route.request().headers(),
        "x-platform-ingress-key": "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii",
        "x-platform-visitor-ip": "203.0.113.7",
      },
    });
  });
  const account = await createSignedInAdmin(page.request, newAccount(level));
  const made = await page.request.post(`${API}/e2e/platform-admin`, {
    headers: await csrfHeaders(page.request),
    data: { email: account.email, level },
  });
  expect(made.status(), await made.text()).toBe(200);

  // Sign in again: the session from sign-up has not passed two-step verification.
  // Each test represents a separate visitor. As with sign-up, use the test API's trusted proxy
  // header so parallel admin tests do not share the five-logins-per-minute IP allowance.
  const visitor = `10.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${1 + Math.floor(Math.random() * 254)}`;
  const login = await page.request.post(`${API}/auth/login`, {
    headers: { ...(await csrfHeaders(page.request)), "X-Real-IP": visitor },
    data: { email: account.email, password: account.password },
  });
  expect(login.status(), await login.text()).toBe(200);
  const challenge = await page.request.post(`${API}/auth/mfa/challenge`, {
    headers: await csrfHeaders(page.request),
    data: { code: totp(PLATFORM_TOTP_SECRET) },
  });
  expect(challenge.status(), await challenge.text()).toBe(200);

  const started = await page.request.post(`${API}/auth/platform-session`, {
    headers: await csrfHeaders(page.request),
  });
  expect(started.status(), await started.text()).toBe(201);
  const cookie = (await page.context().cookies(API)).find((item) => item.name === PLATFORM_COOKIE);
  if (!cookie) throw new Error("the API did not set the platform cookie");
  await page.context().addCookies([{ ...cookie, domain: ADMIN_HOST, path: "/" }]);
  return account;
}
