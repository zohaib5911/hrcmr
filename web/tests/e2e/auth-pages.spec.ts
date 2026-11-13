import { brand } from "@brand";
/**
 * The sign-in screens (plan T3.1), in a real browser against the production build: each one at the
 * four design widths in both themes has no sideways scroll, no console errors, and passes axe; and
 * the keyboard reaches everything in a sensible order.
 *
 * The invitation page asks the API about its token on load, so that one request is answered here.
 */
import { expect, test, type Page } from "@playwright/test";

import { PAGES, answerApi } from "../support/auth-screens";
import { expectBrandLogo } from "../support/brand";

import { audit } from "../support/axe";

// These are the screens for someone who is not signed in.
test.use({ storageState: { cookies: [], origins: [] } });

const WIDTHS = [390, 768, 1280, 1920] as const;

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
          await expectBrandLogo(page.locator("header"), colorScheme);
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
          element.querySelector("img")?.alt ??
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
    brand.name,
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
