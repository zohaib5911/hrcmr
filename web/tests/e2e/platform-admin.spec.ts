import { expect, test } from "@playwright/test";

import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";

// The admin host (T17.1): a platform admin's pages, with the red bar. C3.1.3 seeds the admins; the
// screens themselves come with C3.1.4 to C3.1.10.
test.describe("platform admin host", () => {
  test("a platform owner is let in and sees the admin page with the red bar", async ({ page }) => {
    await signInPlatformAdmin(page, "owner");
    await page.goto(`${ADMIN_ORIGIN}/`);
    await expect(page.getByRole("heading", { level: 1, name: "Platform admin" })).toBeVisible();
    await expect(page.getByTestId("platform-bar")).toContainText("Platform admin");
  });

  test("a support admin is let in the same way", async ({ page }) => {
    await signInPlatformAdmin(page, "support");
    await page.goto(`${ADMIN_ORIGIN}/`);
    await expect(page.getByRole("heading", { level: 1, name: "Platform admin" })).toBeVisible();
    await expect(page.getByTestId("platform-bar")).toBeVisible();
  });

  test("without a platform session the admin host sends the browser to start one, and a start that fails shows the refusal page", async ({
    page,
  }) => {
    // No platform cookie: the frame sends the browser to /session. Its start is a cross-site call
    // from this host to the API, so it is refused, and the refusal page says why.
    await page.goto(`${ADMIN_ORIGIN}/`);
    await expect(page).toHaveURL(/\/session-required\?code=/);
    await expect(
      page.getByRole("heading", { level: 1, name: "Platform session not started" }),
    ).toBeVisible();
  });
});
