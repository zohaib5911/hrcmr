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

const PAGES = [
  { name: "sign in", path: "/login", heading: "Sign in" },
  { name: "two-step verification", path: "/login/mfa", heading: "Two-step verification" },
  { name: "forgot password", path: "/forgot-password", heading: "Forgot your password?" },
  {
    name: "reset password",
    path: "/reset-password?token=example",
    heading: "Choose a new password",
  },
  { name: "link not usable", path: "/verify-email", heading: "Confirm your email address" },
  {
    name: "accept invitation",
    path: "/accept-invite?token=example",
    heading: "Accept your invitation",
  },
] as const;

async function answerInvitation(page: Page) {
  await page.route("**/auth/invitations/example", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": new URL(page.url() || "http://127.0.0.1:3100").origin,
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify({
        company_name: "Harbourside Care Ltd",
        email: "tom@example.com",
        role: "hr_admin",
        expires_at: "2030-01-01T00:00:00Z",
        has_account: false,
      }),
    }),
  );
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
          await answerInvitation(page);
          const problems = await open(page, screen.path, screen.heading);
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
