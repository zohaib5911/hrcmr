/**
 * The signed-in app (plan T3.4), against the real API and a real account (see auth.setup.ts): the
 * sidebar and toolbar know the person and their company, the free-plan banner can be put away for the
 * visit, signing out ends the session, and nobody signed out can open an app page.
 */
import { expect, test } from "@playwright/test";

import { createSignedInAdmin } from "../support/accounts";

test("the shell shows the person, their role, the company and its plan, and the whole menu", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
  const sidebar = page.locator("#app-sidebar");
  await expect(sidebar.getByText(/^Harbourside Care/).first()).toBeVisible();
  await expect(sidebar.getByText("Free", { exact: true })).toBeVisible();
  await expect(sidebar.getByText("Amira Hassan")).toBeVisible();
  await expect(sidebar.getByText("Company Admin")).toBeVisible();
  // A Company Admin can use every page.
  for (const name of ["Employees", "Recruitment", "Reports", "User access", "Billing"]) {
    await expect(sidebar.getByRole("link", { name, exact: true })).toBeVisible();
  }
});

test("the free-plan banner offers to subscribe and can be put away for the visit", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await page.waitForLoadState("networkidle");
  const banner = page.getByRole("status").filter({ hasText: "You're on the free plan" });
  await expect(banner).toBeVisible();
  await expect(banner.getByRole("link", { name: "Subscribe" })).toHaveAttribute(
    "href",
    "/company/billing",
  );
  await banner.getByRole("button", { name: "Dismiss" }).click();
  await expect(banner).toBeHidden();
  await page.goto("/leave");
  await expect(page.getByRole("heading", { level: 1, name: "Leave" })).toBeVisible();
  await expect(page.getByText("You're on the free plan")).toBeHidden();
});

test("signing out ends the session, and the app then sends everyone to sign in", async ({
  page,
}) => {
  // A session of its own, so signing out does not end the one the other tests share.
  const own = await createSignedInAdmin(page.request);
  expect(own.email).toContain("@example.com");

  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("an app page sends the visitor to sign in", async ({ page }) => {
    await page.goto("/employees");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  });
});
