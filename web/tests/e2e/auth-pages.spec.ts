/**
 * The sign-in screens (plan T3.1), in a real browser against the production build: each one at the
 * four design widths in both themes has no sideways scroll, no console errors, and passes axe; and
 * the keyboard reaches everything in a sensible order.
 *
 * The invitation page asks the API about its token on load, so that one request is answered here.
 */
import { expect, test, type Page } from "@playwright/test";

import { audit } from "../support/axe";

const WIDTHS = [390, 768, 1280, 1920] as const;

interface Screen {
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

const PAGES: readonly Screen[] = [
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

async function answerApi(page: Page) {
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

async function open(page: Page, path: string, heading: string) {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(error.message));
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await page.waitForLoadState("networkidle");
  return problems;
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const screen of PAGES) {
      for (const width of WIDTHS) {
        test(`${screen.name} at ${width} px has no sideways scroll, no errors, and passes axe`, async ({
          page,
        }) => {
          await page.setViewportSize({ width, height: 900 });
          await page.goto("/login"); // any page on the site, so the mock knows the page's origin
          await answerApi(page);
          const problems = await open(page, screen.path, screen.heading);
          if (screen.prepare) await screen.prepare(page);
          if (screen.then) {
            await expect(page.getByRole("heading", { level: 1, name: screen.then })).toBeVisible();
          }
          if (screen.name === "accept invitation") {
            await expect(
              page.getByRole("button", { name: "Join Harbourside Care Ltd" }),
            ).toBeVisible();
          }
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          );
          expect(overflow).toBeLessThanOrEqual(0);
          await audit(page, `${colorScheme} ${screen.name} ${width}px`);
          expect(problems).toEqual([]);
        });
      }
    }
  });
}

test("the keyboard reaches every control on the sign-in page in reading order", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  const reached: string[] = [];
  for (let step = 0; step < 10; step++) {
    await page.keyboard.press("Tab");
    reached.push(
      await page.evaluate(() => {
        const element = document.activeElement as HTMLElement;
        const label = element.id ? document.querySelector(`label[for="${element.id}"]`) : null;
        return (
          label?.textContent ??
          element.getAttribute("aria-label") ??
          element.textContent ??
          ""
        )
          .trim()
          .replace(/\s+/g, " ");
      }),
    );
  }
  expect(reached).toEqual([
    "Skip to content",
    "Brand",
    "United Kingdom",
    "USAComing soon",
    "AustraliaComing soon",
    "Email address",
    "Password",
    "Show password",
    "Forgot password?",
    "Sign in",
  ]);
});
