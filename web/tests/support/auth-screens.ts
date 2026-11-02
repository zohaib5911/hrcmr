/**
 * The sign-in screens as a list (shared by the accessibility checks and the screenshots), and the
 * answers the page needs from the API for the screens that ask it something on load or on submit.
 * Everything here runs against the production build with the API's replies faked for those requests.
 */
import { expect, type Page } from "@playwright/test";

export interface Screen {
  name: string;
  path: string;
  heading: string;
  /** What to do on the page to reach the state under test. */
  prepare?: (page: Page) => Promise<void>;
  /** A field that shows once `prepare` is done. */
  ready?: string;
  /** The heading once `prepare` is done, when it changes. */
  then?: string;
}

export const PAGES: readonly Screen[] = [
  { name: "sign in", path: "/login", heading: "Sign in" },
  { name: "two-step verification", path: "/login/mfa", heading: "Two-step verification" },
  { name: "forgot password", path: "/forgot-password", heading: "Forgot your password?" },
  {
    name: "reset password",
    path: "/reset-password?token=example",
    heading: "Choose a new password",
  },
  { name: "link not usable", path: "/verify-email", heading: "Confirm your email address" },
  { name: "set up, company step", path: "/setup", heading: "Create your company account" },
  {
    name: "set up, account step",
    path: "/setup",
    heading: "Create your company account",
    prepare: firstStep,
    ready: "Work email",
  },
  {
    name: "set up, check your inbox",
    path: "/setup",
    heading: "Create your company account",
    prepare: createAccount,
    then: "Check your inbox",
  },
  {
    name: "two-step set-up, scan",
    path: "/mfa/enrol",
    heading: "Set up two-step verification",
    prepare: scanned,
  },
  {
    name: "two-step set-up, recovery codes",
    path: "/mfa/enrol",
    heading: "Set up two-step verification",
    prepare: async (page) => {
      await scanned(page);
      await page.getByLabel("6-digit code", { exact: true }).fill("123456");
      await page.getByRole("button", { name: "Confirm" }).click();
      await expect(page.getByRole("list", { name: "Recovery codes" })).toBeVisible();
    },
  },
  {
    name: "accept invitation",
    path: "/accept-invite?token=example",
    heading: "Accept your invitation",
  },
];

/** Answers one API request from the page (and the browser's permission check before a POST). */
async function answer(page: Page, pattern: string, status: number, body: unknown) {
  await page.route(pattern, (route) => {
    const request = route.request();
    const headers = {
      "access-control-allow-origin": new URL(page.url()).origin,
      "access-control-allow-credentials": "true",
      "access-control-allow-headers": "content-type, x-csrf-token, x-request-id",
    };
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    return route.fulfill({
      status,
      contentType: "application/json",
      headers,
      body: JSON.stringify(body),
    });
  });
}

export async function answerApi(page: Page) {
  await answer(page, "**/auth/invitations/example", 200, {
    company_name: "Harbourside Care Ltd",
    email: "tom@example.com",
    role: "hr_admin",
    expires_at: "2030-01-01T00:00:00Z",
    has_account: false,
  });
  await answer(page, "**/auth/signup", 202, { status: "check_your_inbox" });
  await answer(page, "**/auth/mfa/setup", 200, {
    secret: "JBSWY3DPEHPK3PXP",
    otpauth_uri: "otpauth://totp/Brand:amira@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Brand",
  });
  await answer(page, "**/auth/mfa/verify", 200, {
    recovery_codes: Array.from({ length: 10 }, (_, index) => `rc${index}ab-${index}cdef`),
  });
}

async function scanned(page: Page) {
  await expect(page.getByAltText("QR code for your authenticator app")).toBeVisible();
}

async function firstStep(page: Page) {
  await page.getByLabel("Company name", { exact: true }).fill("Harbourside Care Ltd");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByLabel("Work email", { exact: true })).toBeVisible();
}

async function createAccount(page: Page) {
  await firstStep(page);
  await page.getByLabel("First name", { exact: true }).fill("Amira");
  await page.getByLabel("Last name", { exact: true }).fill("Hassan");
  await page.getByLabel("Work email", { exact: true }).fill("amira@example.com");
  await page.getByLabel("Password", { exact: true }).fill("a long enough password");
  await page.getByRole("checkbox").click();
  await page.getByRole("button", { name: "Create account" }).click();
}
