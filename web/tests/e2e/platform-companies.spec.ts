import { expect, test } from "@playwright/test";
import { API, csrfHeaders } from "../support/accounts";
import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";

// Local admin-host CSP permits server rendering only; client actions are covered in companies.test.tsx.
test("owner sees company detail and persisted suspend/reactivate status", async ({ page }) => {
  const account = await signInPlatformAdmin(page, "owner");
  const list = await page.request.get(`${API}/platform/companies`, {
    params: { q: account.company },
  });
  expect(list.status()).toBe(200);
  const companies = (await list.json()).items;
  expect(companies.length).toBeGreaterThan(0);
  const company =
    companies.find((item: { contact_email: string }) => item.contact_email === account.email) ??
    companies[0];
  await page.goto(`${ADMIN_ORIGIN}/companies?q=${encodeURIComponent(company.name)}`);
  await expect(page.getByRole("heading", { name: "Companies", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: company.name, exact: true })).toBeVisible();
  for (const [action, status] of [
    ["suspend", "suspended"],
    ["reactivate", "active"],
  ] as const) {
    const result = await page.request.post(`${API}/platform/companies/${company.id}/${action}`, {
      headers: await csrfHeaders(page.request),
      data: { reason: "E2E support investigation" },
    });
    expect(result.status(), await result.text()).toBe(200);
    await page.goto(`${ADMIN_ORIGIN}/companies/${company.id}`);
    await expect(page.getByRole("heading", { name: company.name, exact: true })).toBeVisible();
    await expect(page.getByText(status, { exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Mark for deletion" })).toBeVisible();
});

test("support admin does not see owner-only company controls", async ({ page }) => {
  const account = await signInPlatformAdmin(page, "support");
  const list = await page.request.get(`${API}/platform/companies`, {
    params: { q: account.company },
  });
  expect(list.status()).toBe(200);
  const company = (await list.json()).items[0];
  await page.goto(`${ADMIN_ORIGIN}/companies/${company.id}`);
  await expect(page.getByRole("heading", { name: company.name, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark for deletion" })).toHaveCount(0);
});
