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
  await expect(page.getByRole("grid", { name: "Platform audit events" })).toBeVisible();
  // Admin GET filters must also work with the production CSP blocking local HTTP scripts.
  await page.getByLabel("From date (UTC)", { exact: true }).fill("2026-01-01");
  await page.getByLabel("To date (UTC)", { exact: true }).fill("2026-12-31");
  // On the local HTTP host, upgrade-insecure-requests upgrades native form navigation to HTTPS.
  // Read the native form's wire values and load its GET URL directly; HTTPS interaction stays at P25.
  const query = await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .evaluate((button) => {
      const form = (button as HTMLButtonElement).form!;
      return new URLSearchParams(
        Array.from(new FormData(form), ([key, value]) => [key, String(value)]),
      ).toString();
    });
  await page.goto(`${ADMIN_ORIGIN}/audit?${query}`);
  await expect(page).toHaveURL(/since=2026-01-01&until=2026-12-31/);
  await expect(page.getByRole("grid", { name: "Platform audit events" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    /\/platform\/audit\/export\?action=platform\.&actor_type=platform_admin/,
  );
});
