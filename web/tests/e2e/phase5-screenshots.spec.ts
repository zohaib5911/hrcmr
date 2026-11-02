/**
 * Design QA screenshots of User Access (plan 5.12 and Phase 5), in light and dark at 1280 px and
 * 390 px: the page, the invite sheet and the role viewer. They are the evidence kept in
 * docs/screenshots/phase-5/, so this runs only on request:
 *
 *   SCREENSHOTS=1 pnpm exec playwright test phase5-screenshots --project=production
 */
import path from "node:path";

import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-5");
const SIZES = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "phone", width: 390, height: 844 },
] as const;

test.skip(!process.env.SCREENSHOTS, "Screenshots are only taken on request (SCREENSHOTS=1).");

async function shoot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.mouse.move(0, 0);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const size of SIZES) {
      test(`user access (${size.name})`, async ({ page }) => {
        await page.setViewportSize({ width: size.width, height: size.height });
        await page.goto("/company/users");
        await expect(page.getByRole("heading", { level: 1, name: "User access" })).toBeVisible();
        await page.waitForLoadState("networkidle");
        const suffix = `${colorScheme}-${size.name}`;
        await shoot(page, `user-access-${suffix}`);

        await page.getByRole("button", { name: "Invite user" }).click();
        await expect(page.getByRole("dialog", { name: "Invite user" })).toBeVisible();
        await shoot(page, `invite-sheet-${suffix}`);
        await page.keyboard.press("Escape");

        await page.getByRole("button", { name: "What can each role do?" }).click();
        await expect(page.getByRole("dialog", { name: "What can each role do?" })).toBeVisible();
        await shoot(page, `role-viewer-${suffix}`);
      });
    }
  });
}
