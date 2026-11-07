/** Phase 15 gate: the sponsorship checker and its free version at 390/1280 px in light and dark. */
import path from "node:path";

import { type Page } from "@playwright/test";

import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-15");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");

async function shoot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  await audit(page, name);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`Sponsorship checker at ${width}px`, async ({ page }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/sponsorship-checker");
        await expect(page.getByRole("heading", { name: "Sponsorship job checker" })).toBeVisible();
        await page.waitForLoadState("networkidle");
        await shoot(page, `checker-empty-${colorScheme}-${width}`);

        await page.getByRole("textbox", { name: "Job title" }).fill("Adviser, sales");
        await page.getByLabel("Offered salary", { exact: true }).fill("30000");
        await page.getByRole("button", { name: "Check this job" }).click();
        await page.getByRole("button", { name: "Check this code" }).first().click();
        await expect(
          page.getByRole("heading", { name: "7111 Sales and retail assistants" }),
        ).toBeVisible();
        await shoot(page, `checker-saved-${colorScheme}-${width}`);
      });

      test(`Free checker at ${width}px`, async ({ page }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/resources/tools/sponsorship-job-checker");
        await expect(
          page.getByRole("heading", { level: 1, name: "Sponsorship job checker" }),
        ).toBeVisible();
        await page.getByRole("textbox", { name: "Job title" }).fill("Adviser, sales");
        await page.getByRole("button", { name: /^7111 Sales and retail assistants$/ }).click();
        await page.getByLabel("Offered salary", { exact: true }).fill("30000");
        await page.getByRole("button", { name: "Show the salary table" }).click();
        await expect(page.getByRole("region", { name: "Salary table" })).toBeVisible();
        await shoot(page, `free-checker-${colorScheme}-${width}`);
      });
    }
  });
}
