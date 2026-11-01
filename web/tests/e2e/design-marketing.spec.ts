/**
 * The pricing cards and the headcount slider (plan T1.5), on the development-only /design/marketing
 * page, because the production site has no prices to show until T18.1.
 */
import { expect, test } from "@playwright/test";

import { audit } from "../support/axe";

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test("the plan cards and the slider pass axe", async ({ page }) => {
      await page.goto("/design/marketing");
      await page.locator("html[data-hydrated]").waitFor({ state: "attached" });
      await expect(page.getByText("Best value")).toBeVisible();
      await audit(page, `${colorScheme} pricing`);
    });
  });
}

test("the slider moves with the arrow keys and the price per person falls", async ({ page }) => {
  await page.goto("/design/marketing");
  await page.locator("html[data-hydrated]").waitFor({ state: "attached" });
  const thumb = page.getByRole("slider", { name: "How many people work for you?" });
  await expect(page.getByText("10 people")).toBeVisible();
  await expect(page.getByText("£5.00").first()).toBeVisible(); // £50 a year over 10 people
  await expect(page.getByText("£2.40").first()).toBeVisible(); // £240 over ten years, over 10 people
  await thumb.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByText("11 people")).toBeVisible();
  await page.keyboard.press("End");
  await expect(page.getByText("250 people")).toBeVisible();
  await expect(page.getByText("£0.20").first()).toBeVisible(); // £50 over 250 people
});
