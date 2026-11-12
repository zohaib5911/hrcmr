import { expect, test } from "@playwright/test";
import { audit } from "../support/axe";

test.use({ storageState: { cookies: [], origins: [] } });
for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} resources`, () => {
    test.use({ colorScheme });
    for (const [route, heading] of [
      ["/resources", "Employer resources"],
      ["/resources/guides", "Employer guides"],
      ["/resources/tools", "Free employer tools"],
      ["/resources/templates", "Employer templates"],
    ]) {
      test(`${route} opens signed out with working category navigation`, async ({ page }) => {
        const response = await page.goto(route);
        expect(response?.status()).toBe(200);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        await page
          .locator('[data-consent-state]:not([data-consent-state="loading"])')
          .waitFor({ state: "attached" });
        await audit(page, `${colorScheme} ${route}`);
        const categories = page.getByRole("navigation", { name: "Resource categories" });
        await categories.getByRole("link", { name: "Guides", exact: true }).click();
        await expect(
          page.getByRole("heading", { level: 1, name: "Employer guides" }),
        ).toBeVisible();
        await page
          .getByRole("main")
          .getByRole("link", { name: "Sponsor licence audit preparation", exact: true })
          .click();
        await expect(
          page.getByRole("heading", { level: 1, name: "Sponsor licence audit preparation" }),
        ).toBeVisible();
      });
    }
  });
}
