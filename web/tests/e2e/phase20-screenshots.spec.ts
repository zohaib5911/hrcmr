/** Phase 20 gate: real saved publications rendered by the public register pages. */
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { API } from "../support/accounts";
import { audit } from "../support/axe";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-20");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");
test.use({ storageState: { cookies: [], origins: [] } });

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
      test(`sponsor register at ${width}px`, async ({ page }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const response = await page.request.get(`${API}/public/register/sitemap/0`);
        expect(response.status()).toBe(200);
        const { items } = (await response.json()) as {
          items: { stable_id: string; slug: string }[];
        };
        const active = items.find((s) => s.slug === "stable-ltd");
        const removed = items.find((s) => s.slug === "gone-ltd");
        expect(active).toBeTruthy();
        expect(removed).toBeTruthy();

        await page.goto("/sponsors");
        await page.getByRole("button", { name: "Reject all", exact: true }).click();
        await expect(
          page.getByRole("status").filter({ hasText: "3 matching sponsors" }),
        ).toBeVisible();
        await shoot(page, `explore-map-${suffix}`);
        for (const view of ["Trend", "Table", "List"] as const) {
          await page.getByRole("button", { name: view, exact: true }).click();
          await shoot(page, `explore-${view.toLowerCase()}-${suffix}`);
        }
        await page.getByRole("searchbox").fill("no-such-sponsor");
        await page.getByRole("button", { name: "Search register" }).click();
        await expect(page.getByText(/No sponsors match these filters/)).toBeVisible();
        await shoot(page, `explore-empty-${suffix}`);

        for (const [route, heading, name] of [
          ["/sponsors/regions/london", "Licensed sponsors in London", "region"],
          ["/sponsors/changes", "Change bulletins", "bulletins"],
          ["/sponsors/changes/2026-11-11", "Register changes, 11 Nov 2026", "bulletin"],
          [
            `/sponsors/profile/${active!.stable_id}/${active!.slug}`,
            "Stable Ltd",
            "profile-current",
          ],
          [
            `/sponsors/profile/${removed!.stable_id}/${removed!.slug}`,
            "Gone Ltd",
            "profile-removed",
          ],
          ["/sponsors/methodology", "Methodology", "methodology"],
          ["/sponsors/terms", "Register terms", "terms"],
        ]) {
          await page.goto(route);
          await expect(
            page.getByRole("heading", { level: 1, name: heading, exact: true }),
          ).toBeVisible();
          await shoot(page, `${name}-${suffix}`);
        }
      });
    }
  });
}
