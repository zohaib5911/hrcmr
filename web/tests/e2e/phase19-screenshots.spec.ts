/** Phase 19 gate: public resource hubs, guides and tools at 390/1280 px in both themes. */
import path from "node:path";

import { expect, test } from "@playwright/test";

import { audit } from "../support/axe";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-19");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");
test.use({ storageState: { cookies: [], origins: [] } });

const ROUTES = [
  "/resources",
  "/resources/guides",
  "/resources/tools",
  "/resources/templates",
  "/resources/guides/follow-up-right-to-work-checks",
  "/resources/guides/right-to-work-changes-october-2026",
  "/resources/guides/right-to-work-checks",
  "/resources/guides/sponsor-licence-audit-preparation",
  "/resources/guides/sponsor-reporting-duties",
  "/resources/guides/statutory-holiday-entitlement",
  "/resources/tools/holiday-entitlement-calculator",
  "/resources/tools/ilr-citizenship-checker",
  "/resources/tools/right-to-work-october-2026-checker",
  "/resources/tools/risk-assessment-template",
  "/resources/tools/skilled-worker-ilr-salary-calculator",
  "/resources/tools/skilled-worker-visa-checker",
  "/resources/tools/sponsor-licence-cost-calculator",
  "/resources/tools/sponsor-reporting-deadline-calculator",
  "/resources/tools/sponsorship-job-checker",
  "/resources/tools/uk-employer-cost-calculator",
  "/resources/tools/uk-minimum-wage-underpayment-checker",
  "/resources/tools/uk-notice-pay-calculator",
  "/resources/tools/uk-redundancy-pay-calculator",
  "/resources/tools/uk-sick-pay-calculator",
  "/resources/tools/uk-take-home-salary-calculator",
] as const;

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      for (const route of ROUTES) {
        test(`${route} at ${width}px`, async ({ page }) => {
          await page.setViewportSize({ width, height: 900 });
          const response = await page.goto(route);
          expect(response?.status()).toBe(200);
          await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
          await page
            .locator('[data-consent-state]:not([data-consent-state="loading"])')
            .waitFor({ state: "attached" });
          await page.evaluate(() => document.fonts.ready);
          await page.mouse.move(0, 0);
          const name = `${route.slice(1).replaceAll("/", "-")}-${colorScheme}-${width}`;
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
        });
      }
    }
  });
}
