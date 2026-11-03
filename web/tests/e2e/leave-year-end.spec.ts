/** T8.5 preview, reasoned override, reviewed commit and persisted closed-year history. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("review and commit year-end carry-over with an exception", async ({ page, context }) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const pattern = await api.put(`${API}/working-pattern`, {
    headers,
    data: {
      days: Array.from({ length: 7 }, (_, i) => ({
        weekday: i + 1,
        is_working: i < 5,
        hours: i < 5 ? "8" : "0",
      })),
      bank_holidays_non_working: false,
    },
  });
  expect(pattern.status(), await pattern.text()).toBe(200);
  const employee = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Mira",
      last_name: "Carry",
      email: "mira@example.com",
      employee_number: "CARRY1",
      hire_date: "2025-01-01",
    },
  });
  expect(employee.status(), await employee.text()).toBe(201);
  await page.goto("/leave/settings");
  await page.getByRole("link", { name: "Year end", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Leave year end" })).toBeVisible();
  await page.getByLabel("Leave year starts", { exact: true }).fill("2025-01-01");
  await page.getByRole("button", { name: "Preview year", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "5 days to carry forward" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Override Annual Leave", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Override Annual Leave", exact: true });
  await sheet.getByLabel("Carry-over days", { exact: true }).fill("8");
  await sheet
    .getByLabel("Override reason", { exact: true })
    .fill("Reviewed family leave exception");
  await sheet.getByRole("button", { name: "Apply override", exact: true }).click();
  await expect(sheet).toBeHidden();
  await expect(
    page.getByRole("status").filter({ hasText: "8 days to carry forward" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Commit year end", exact: true }).click();
  await page.getByRole("button", { name: "Close leave year", exact: true }).click();
  await expect(page.getByText("Leave year closed", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Commit year end", exact: true })).toHaveCount(0);
  await page.reload();
  await page.getByLabel("Leave year starts", { exact: true }).fill("2025-01-01");
  await page.getByRole("button", { name: "Preview year", exact: true }).click();
  await expect(page.getByText("Leave year closed", { exact: true })).toBeVisible();
  await expect(page.getByText("Reviewed family leave exception", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Year-end history mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
