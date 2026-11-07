/** Phase 14 gate: the dashboard, the notifications list and the command palette, at 390/1280 px in light and dark. */
import path from "node:path";
import { type Page, request } from "@playwright/test";
import { createSignedInAdmin } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-14");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");
// A fresh company keeps the visual states identical instead of accumulating seed data.
test.use({
  storageState: async ({}, use) => {
    const api = await request.newContext();
    try {
      await createSignedInAdmin(api);
      // eslint-disable-next-line react-hooks/rules-of-hooks -- Playwright fixture callback.
      await use(await api.storageState());
    } finally {
      await api.dispose();
    }
  },
});

async function shoot(page: Page, name: string, modal = false) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  await audit(page, name, { modal });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: !modal,
    animations: "disabled",
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`Dashboard, notifications and search at ${width}px`, async ({ page }) => {
        test.setTimeout(240_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;

        await page.goto("/dashboard");
        await expect(
          page.getByRole("heading", { name: "Dashboard", level: 1, exact: true }),
        ).toBeVisible();
        await shoot(page, `dashboard-${suffix}`);

        await page.goto("/dashboard");
        await page
          .getByRole("button", { name: /^Notifications/ })
          .first()
          .click();
        await expect(
          page.getByRole("heading", { name: "Notifications", level: 2, exact: true }),
        ).toBeVisible();
        await shoot(page, `notifications-${suffix}`, true);
        await page.keyboard.press("Escape");

        await page.goto("/dashboard");
        await page.keyboard.press("Control+k");
        await expect(page.getByPlaceholder("Search pages")).toBeVisible();
        await page.keyboard.type("leave");
        await shoot(page, `search-${suffix}`, true);
        await page.keyboard.press("Escape");
      });
    }
  });
}
