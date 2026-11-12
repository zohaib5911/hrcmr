import { expect, test } from "@playwright/test";
import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";
// The recorded C3.1.4–C3.1.10 decision assigns browser actions to mocked unit tests;
// local admin-host CSP permits only server-rendered browser checks.
test("an owner opens settings and sees all three sections", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.goto(`${ADMIN_ORIGIN}/settings`);
  await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  for (const name of ["Terms versions", "Feature flags", "Announcements"])
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  await expect(page.getByRole("button", { name: "Publish new version" })).toBeVisible();
});
test("support cannot publish terms", async ({ page }) => {
  await signInPlatformAdmin(page, "support");
  await page.goto(`${ADMIN_ORIGIN}/settings`);
  await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Publish new version" })).toHaveCount(0);
});
