/**
 * The pay settings (plan T4.7), against the real API and a real signed-in Company Admin: add one of
 * each, see it listed, and check the bank account shows only masked numbers.
 */
import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

import { audit } from "../support/axe";

test.describe.configure({ mode: "serial" });

async function open(page: Page, path: string, heading: string) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("a bank account is added and only ever shown masked", async ({ page }) => {
  await open(page, "/company/bank-accounts", "Bank accounts");
  await expect(page.getByText("No bank accounts yet")).toBeVisible();
  await page.getByRole("button", { name: "Add bank account" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Add bank account" });
  await sheet.getByLabel("Label", { exact: true }).fill("Wages account");
  await sheet.getByLabel("Bank", { exact: true }).fill("Example Bank");
  await sheet.getByLabel("Name on the account", { exact: true }).fill("Harbourside Care Ltd");
  await sheet.getByLabel("Sort code", { exact: true }).fill("12-34");
  await sheet.getByLabel("Account number", { exact: true }).fill("87654321");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(sheet.getByText("A sort code is 6 digits")).toBeVisible();
  await sheet.getByLabel("Sort code", { exact: true }).fill("12-34-56");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  const row = page.getByRole("button", { name: /Wages account \(main\)/ });
  await expect(row).toContainText("••-••-56");
  await expect(row).toContainText("••••4321");
  await expect(page.locator("body")).not.toContainText("87654321");
  await audit(page, "bank accounts");
});

test("a tax code, payment type, pay band and pay schedule can each be added", async ({ page }) => {
  await open(page, "/company/tax-codes", "Tax codes");
  await page.getByRole("button", { name: "Add tax code" }).first().click();
  let sheet = page.getByRole("dialog", { name: "Add tax code" });
  await sheet.getByLabel("Code", { exact: true }).fill("1257l");
  await sheet.getByLabel("Deduction", { exact: true }).fill("20");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: /1257L/ })).toContainText("20%");
  await audit(page, "tax codes");

  await open(page, "/company/payment-types", "Payment types");
  await page.getByRole("button", { name: "Add payment type" }).first().click();
  sheet = page.getByRole("dialog", { name: "Add payment type" });
  await sheet.getByLabel("Name", { exact: true }).fill("Hourly");
  await sheet.getByLabel("Minimum hourly rate", { exact: true }).fill("12.50");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: /Hourly/ })).toContainText("From £12.50 an hour");

  await open(page, "/company/pay-bands", "Pay bands");
  await page.getByRole("button", { name: "Add pay band" }).first().click();
  sheet = page.getByRole("dialog", { name: "Add pay band" });
  await sheet.getByLabel("Name", { exact: true }).fill("Grade 3");
  await sheet.getByLabel("Lowest yearly pay", { exact: true }).fill("34000");
  await sheet.getByLabel("Highest yearly pay", { exact: true }).fill("28000");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(sheet.getByText("The highest cannot be less than the lowest.")).toBeVisible();
  await sheet.getByLabel("Lowest yearly pay", { exact: true }).fill("28000");
  await sheet.getByLabel("Highest yearly pay", { exact: true }).fill("34000");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: /Grade 3/ })).toContainText(
    "£28,000 to £34,000 a year",
  );

  await open(page, "/company/pay-schedules", "Pay schedules");
  await page.getByRole("button", { name: "Add pay schedule" }).first().click();
  sheet = page.getByRole("dialog", { name: "Add pay schedule" });
  await sheet.getByLabel("Name", { exact: true }).fill("Monthly wages");
  await sheet.getByLabel("Pay day", { exact: true }).selectOption({ label: "A day of the month" });
  await sheet.getByLabel("Day of the month", { exact: true }).fill("25");
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: /Monthly wages/ })).toContainText(
    "Monthly, on the 25th",
  );
  await audit(page, "pay schedules");
});

test("the overview links to all five", async ({ page }) => {
  await open(page, "/company", "Company");
  for (const name of [
    "Bank accounts",
    "Tax codes",
    "Payment types",
    "Pay bands",
    "Pay schedules",
  ]) {
    await expect(page.getByRole("link", { name: new RegExp(name) })).toBeVisible();
  }
});
