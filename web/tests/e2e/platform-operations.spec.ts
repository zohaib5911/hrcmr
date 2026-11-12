import { expect, test } from "@playwright/test";
import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";
// Admin-host actions use mocked unit tests per the C3.1.4–C3.1.10 decision.
test("an owner opens jobs and filters the platform audit log", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.goto(`${ADMIN_ORIGIN}/jobs`);
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
  await expect(page.getByText(/Waiting in queue:/)).toBeVisible();
  await expect(page.getByText("No failed jobs.")).toBeVisible();
  await page.goto(`${ADMIN_ORIGIN}/audit?action=platform.&actor_type=platform_admin`);
  await expect(
    page.getByRole("heading", { name: "Platform audit log", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table", { name: "Platform audit events" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    /\/platform\/audit\/export\?action=platform\.&actor_type=platform_admin/,
  );
});
