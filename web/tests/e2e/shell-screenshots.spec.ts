/**
 * Design QA screenshots of the app shell (plan 5.12 and T1.3): four widths in light and dark, plus
 * the collapsed sidebar and the phone "More" sheet. They are the evidence kept in
 * docs/screenshots/phase-1/, so this runs only when asked, and normal test runs never rewrite them:
 *
 *   SCREENSHOTS=1 pnpm exec playwright test shell-screenshots --project=production
 */
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-1");
const WIDTHS = [390, 768, 1280, 1920] as const;

test.skip(!process.env.SCREENSHOTS, "Screenshots are only taken on request (SCREENSHOTS=1).");

async function ready(page: Page, route: string) {
  await page.goto(route);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  // Let the page settle: no hover, no transition in flight.
  await page.mouse.move(0, 0);
  await page.waitForTimeout(400);
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });

    for (const width of WIDTHS) {
      test(`shell at ${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
        await ready(page, "/sponsor-compliance/reminders");
        await page.screenshot({ path: path.join(OUT, `shell-${colorScheme}-${width}.png`) });
      });
    }

    test("shell with the sidebar collapsed", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await ready(page, "/employees");
      await page.keyboard.press("[");
      await expect
        .poll(async () =>
          Math.round((await page.locator("#app-sidebar").boundingBox())?.width ?? 0),
        )
        .toBe(72);
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(OUT, `shell-${colorScheme}-collapsed.png`) });
    });

    test("phone More sheet", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await ready(page, "/employees");
      await page.getByRole("button", { name: "More" }).click();
      await expect(page.getByRole("dialog", { name: "More" })).toBeVisible();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(OUT, `shell-${colorScheme}-more-sheet.png`) });
    });
  });
}
