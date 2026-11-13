import { expect, test } from "@playwright/test";
import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";

// Client actions are unit-tested under the recorded admin-host CSP policy.
test("a support admin sees the seeded register status and navigation", async ({ page }) => {
  await signInPlatformAdmin(page, "support");
  await page.goto(`${ADMIN_ORIGIN}/`);
  await expect(page.getByRole("link", { name: "Sponsor register", exact: true })).toHaveAttribute(
    "href",
    "/register",
  );
  await page.goto(`${ADMIN_ORIGIN}/register`);
  await expect(page.getByRole("heading", { name: "Sponsor register", exact: true })).toBeVisible();
  await expect(page.getByText("11 Nov 2026", { exact: true })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: /^Rows in publication/ })).toHaveText(
    /^Rows in publication\s*4$/,
  );
  await expect(page.getByText("No recent import errors.")).toBeVisible();
  await expect(page.getByTestId("platform-bar")).toBeVisible();
});

test("register operations require a platform session", async ({ page }) => {
  await page.goto(`${ADMIN_ORIGIN}/register`);
  await expect(page).toHaveURL(/\/session\?next=%2Fregister$/);
  await expect(page.getByRole("heading", { name: "Sponsor register", exact: true })).toHaveCount(0);
});
