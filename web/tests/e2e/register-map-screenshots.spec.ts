// T25.4 evidence: the sponsor register map after the redesign (light and dark, 360/390/1280 px,
// whole UK and zoomed into London). Runs only when SCREENSHOTS is set, like the phase-25 audit.
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-25/after");

test.skip(!process.env.SCREENSHOTS, "Design evidence is explicitly requested.");

for (const colorScheme of ["light", "dark"] as const) {
  for (const width of [360, 390, 1280]) {
    test(`register map ${colorScheme} ${width}`, async ({ browser }) => {
      const context = await browser.newContext({
        colorScheme,
        viewport: { width, height: 2400 },
        storageState: { cookies: [], origins: [] },
      });
      const page = await context.newPage();
      await page.goto("/sponsors");
      const reject = page.getByRole("button", { name: "Reject all" });
      await reject.click({ timeout: 5000 }).catch(() => undefined);
      await page.mouse.move(0, 0);
      const map = page.getByRole("group", { name: /Map of UK regions/ });
      await expect(map).toBeVisible();
      const view = page.locator('section[aria-label="Map view"]');
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
        width,
      );
      expect(
        (await new AxeBuilder({ page }).include('section[aria-label="Map view"]').analyze())
          .violations,
      ).toEqual([]);
      await view.screenshot({ path: path.join(OUT, `sponsors-map-${colorScheme}-${width}.png`) });
      const london = page.getByRole("button", { name: /^London: / });
      await london.focus();
      await page.keyboard.press("Enter");
      await expect(london).toHaveAttribute("aria-pressed", "true");
      await page.waitForTimeout(500);
      await view.screenshot({
        path: path.join(OUT, `sponsors-map-london-${colorScheme}-${width}.png`),
      });
      await context.close();
    });
  }
}
