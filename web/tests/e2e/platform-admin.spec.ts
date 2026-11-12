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
    await expect(page.getByText("Active companies")).toBeVisible();
  });

  test("a support admin is let in the same way", async ({ page }) => {
    await signInPlatformAdmin(page, "support");
    await page.goto(`${ADMIN_ORIGIN}/`);
    await expect(page.getByRole("heading", { level: 1, name: "Platform admin" })).toBeVisible();
    await expect(page.getByTestId("platform-bar")).toBeVisible();
  });

  test("without a platform session the admin host sends the browser to the start page", async ({
    page,
  }) => {
    // The start itself runs in the browser. These local tests cannot run client code on the admin host
    // (see tests/support/platform.ts), so this stops at the redirect to the start page.
    await page.goto(`${ADMIN_ORIGIN}/`);
    await expect(page).toHaveURL(/\/session\?next=%2F$/);
  });

  test("the refusal page is shown on the admin host", async ({ page }) => {
    await page.goto(`${ADMIN_ORIGIN}/session-required?code=UNAUTHENTICATED`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Platform session not started" }),
    ).toBeVisible();
  });
});

// C3.1.6: the admin host runs no client JavaScript here, so only the server-rendered page is checked.
// Lock and unlock are covered by components/platform/users-admin.test.tsx with the API mocked.
test("a platform owner opens the users page", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.goto(`${ADMIN_ORIGIN}/users`);
  await expect(page.getByRole("heading", { level: 1, name: "Users" })).toBeVisible();
});

// C3.1.8: server-rendered headings only (no client JavaScript on the admin host in e2e); the lists and
// the empty states are covered by queues-admin.test.tsx and contact-admin.test.tsx.
test("a platform owner opens the queues and contact pages", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.goto(`${ADMIN_ORIGIN}/queues`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Deletion and export queues" }),
  ).toBeVisible();
  await page.goto(`${ADMIN_ORIGIN}/contact`);
  await expect(page.getByRole("heading", { level: 1, name: "Contact messages" })).toBeVisible();
});

// C3.1.7: the refund itself is a unit test (no Stripe in the e2e server); only the page is checked here.
test("a platform owner opens the subscriptions page", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.goto(`${ADMIN_ORIGIN}/subscriptions`);
  await expect(page.getByRole("heading", { level: 1, name: "Subscriptions" })).toBeVisible();
});

test("SSR refuses a visitor outside the admin allowlist", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.route(`${ADMIN_ORIGIN}/**`, async (route) => {
    await route.continue({
      headers: {
        ...route.request().headers(),
        "x-platform-ingress-key": "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii",
        "x-platform-visitor-ip": "198.51.100.9",
      },
    });
  });
  await page.goto(`${ADMIN_ORIGIN}/`);
  await expect(page).toHaveURL(/\/session\?next=%2F$/);
  await expect(page.getByText("Active companies")).toHaveCount(0);
});

test("SSR refuses forged identity headers without authenticated ingress", async ({ page }) => {
  await signInPlatformAdmin(page, "owner");
  await page.route(`${ADMIN_ORIGIN}/**`, async (route) => {
    await route.continue({
      headers: {
        ...route.request().headers(),
        "x-platform-ingress-key": "forged",
        "x-platform-visitor-ip": "203.0.113.7",
        "x-forwarded-for": "203.0.113.7",
      },
    });
  });
  await page.goto(`${ADMIN_ORIGIN}/`);
  await expect(page).toHaveURL(/\/session\?next=%2F$/);
  await expect(page.getByText("Active companies")).toHaveCount(0);
});
