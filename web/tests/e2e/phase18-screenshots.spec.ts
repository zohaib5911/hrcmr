/** Phase 18 screenshots: public marketing pages, both widths and themes. */
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-18");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");

const PAGES = [
  ["/", "home"],
  ["/features", "features"],
  ["/pricing", "pricing"],
  ["/security", "security"],
  ["/about", "about"],
  ["/contact", "contact"],
  ["/accessibility", "accessibility"],
  ["/careers", "careers"],
  ["/sponsor-licence-compliance", "sponsor-compliance"],
  ["/sponsor-licence-compliance/reporting-duties", "reporting-duties"],
  ["/legal/terms", "terms"],
  ["/legal/privacy", "privacy"],
] as const;

async function shoot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.mouse.move(0, 0);
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
      test(`marketing pages at ${width}px`, async ({ page }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height: 900 });
        for (const [route, name] of PAGES) {
          const res = await page.goto(route);
          expect(res?.status(), route).toBeLessThan(400);
          await page.locator("html[data-hydrated]").waitFor({ state: "attached" });
          await shoot(page, `${name}-${colorScheme}-${width}`);
        }
      });
    }
  });
}
