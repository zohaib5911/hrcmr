/**
 * Design QA screenshots of the sign-in screens (plan 5.12 and Phase 3): every screen in light and dark
 * at 1280 px and on a phone (390 px), and the signed-in dashboard with its free-plan banner. They are
 * the evidence kept in docs/screenshots/phase-3/, so this runs only when asked:
 *
 *   SCREENSHOTS=1 pnpm exec playwright test auth-screenshots --project=production
 */
import path from "node:path";

import { expect, test } from "@playwright/test";

import { PAGES, answerApi } from "../support/auth-screens";
import { createSignedInAdmin, newAccount } from "../support/accounts";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-3");
const SIZES = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "phone", width: 390, height: 844 },
] as const;

test.skip(!process.env.SCREENSHOTS, "Screenshots are only taken on request (SCREENSHOTS=1).");

const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, "-");

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });

    test.describe("signed out", () => {
      test.use({ storageState: { cookies: [], origins: [] } });

      for (const size of SIZES) {
        for (const screen of PAGES) {
          test(`${screen.name} (${size.name})`, async ({ page }) => {
            await page.setViewportSize({ width: size.width, height: size.height });
            await page.goto("/login");
            await answerApi(page);
            await page.goto(screen.path);
            await expect(
              page.getByRole("heading", { level: 1, name: screen.heading }),
            ).toBeVisible();
            if (screen.name === "accept invitation") {
              await expect(page.getByRole("button", { name: /^Join / })).toBeVisible();
            }
            if (screen.prepare) await screen.prepare(page);
            if (screen.then) {
              await expect(
                page.getByRole("heading", { level: 1, name: screen.then }),
              ).toBeVisible();
            }
            await page.evaluate(() => document.fonts.ready);
            await page.mouse.move(0, 0);
            await page.waitForTimeout(400);
            await page.screenshot({
              path: path.join(OUT, `${slug(screen.name)}-${colorScheme}-${size.name}.png`),
            });
          });
        }
      }
    });

    for (const size of SIZES) {
      test(`the signed-in dashboard (${size.name})`, async ({ page }) => {
        // A free company of its own, to show the free-plan banner (the shared account is paid).
        await createSignedInAdmin(page.request, newAccount(), { plan: "free" });
        await page.setViewportSize({ width: size.width, height: size.height });
        await page.goto("/dashboard");
        await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
        await expect(page.getByText("You're on the free plan")).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        await page.mouse.move(0, 0);
        await page.waitForTimeout(400);
        await page.screenshot({
          path: path.join(OUT, `dashboard-signed-in-${colorScheme}-${size.name}.png`),
        });
      });
    }
  });
}
