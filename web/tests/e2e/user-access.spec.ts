/**
 * The User Access list (plan T5.1), against the real API and a real signed-in Company Admin: the
 * admin is listed (marked "you"), the unlinked banner counts them, the filters work, and the page
 * passes the accessibility check in both themes at phone and desktop widths.
 */
import { expect, test } from "../support/fixtures";

import { audit } from "../support/axe";

async function open(page: import("@playwright/test").Page) {
  await page.goto("/company/users");
  await expect(page.getByRole("heading", { level: 1, name: "User access" })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("the admin is listed, the banner counts unlinked users, and the filters narrow the list", async ({
  page,
}) => {
  await open(page);
  const table = page.getByRole("grid", { name: "People with access" });
  await expect(table.getByText("Amira Hassan")).toBeVisible();
  await expect(table.getByText("(you)")).toBeVisible();
  await expect(table.getByText("Company Admin")).toBeVisible();
  await expect(page.getByRole("alert").getByText("1 unlinked user")).toBeVisible();
  await expect(page.getByText("1 row", { exact: true })).toBeVisible();

  await page.getByLabel("Role", { exact: true }).selectOption("employee");
  await expect(page.getByText("Nobody matches")).toBeVisible();
  await page.getByLabel("Role", { exact: true }).selectOption("all");
  await page.getByRole("searchbox", { name: "Search people" }).fill("hassan");
  await expect(table.getByText("Amira Hassan")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search people" }).fill("zzz");
  await expect(page.getByText("Nobody matches")).toBeVisible();
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of [390, 1280] as const) {
      test(`the page at ${width} px has no sideways scroll and passes axe`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await audit(page, `${colorScheme} user access ${width}px`);
      });
    }
  });
}
