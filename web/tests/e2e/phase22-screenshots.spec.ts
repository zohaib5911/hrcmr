/** Phase 22 gate: refreshed dashboard evidence after the layout-shift fix. */
import path from "node:path";

import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-22");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`dashboard at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/dashboard");
        await expect(page.getByText("Right to Work coverage (%)", { exact: true })).toBeVisible();
        await expect(page.locator(".skeleton")).toHaveCount(0);
        await page.evaluate(() => document.fonts.ready);
        await audit(page, `Dashboard ${colorScheme} ${width}`);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          ),
        ).toBeLessThanOrEqual(0);
        await page.screenshot({
          path: path.join(OUT, `dashboard-${colorScheme}-${width}.png`),
          fullPage: true,
          animations: "disabled",
        });
      });
    }
  });
}
