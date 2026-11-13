/** T8.1: leave configuration against real seeded tenants and API, including mobile accessibility. */
import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { audit } from "../../support/axe";

test.describe.configure({ mode: "serial" });

async function open(page: Page) {
  await page.goto("/leave/settings");
  await expect(page.getByRole("heading", { level: 1, name: "Leave settings" })).toBeVisible();
}

test("verified defaults, saved settings and type add/edit/archive are usable", async ({ page }) => {
  await page.goto("/leave");
  await page.getByRole("link", { name: "Leave settings", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Leave settings" })).toBeVisible();
  await expect(page.getByText("12 rows", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Leave year starts (MM-DD)", { exact: true })).toHaveValue("01-01");
  await page.getByRole("button", { name: "View guidance for Annual Leave", exact: true }).click();
  const guidance = page.getByRole("dialog", { name: "Annual Leave guidance" });
  await expect(guidance.getByText(/5.6 weeks/)).toBeVisible();
  await expect(guidance.getByRole("link", { name: "GOV.UK source" })).toHaveAttribute(
    "href",
    "https://www.gov.uk/holiday-entitlement-rights",
  );
  await expect(guidance.getByText(/2026-11-03/)).toBeVisible();
  await guidance.getByRole("button", { name: "Close", exact: true }).click();

  const start = page.getByLabel("Leave year starts (MM-DD)", { exact: true });
  await start.fill("04-31");
  await page.getByRole("button", { name: "Save leave settings" }).click();
  await expect(page.getByText(/Use a date that occurs every year/)).toBeVisible();
  await start.fill("04-06");
  await page.getByRole("switch", { name: "Allow negative leave balances" }).click();
  await page.getByRole("button", { name: "Save leave settings" }).click();
  await expect(page.getByText("Leave settings saved", { exact: true })).toBeVisible();
  await page.reload();
  await expect(start).toHaveValue("04-06");
  await expect(page.getByRole("switch", { name: "Allow negative leave balances" })).toBeChecked();

  await page.getByRole("button", { name: "Add leave type" }).click();
  const add = page.getByRole("dialog", { name: "Add leave type" });
  await add.getByRole("button", { name: "Save", exact: true }).click();
  await expect(add.getByText("Enter a leave type name.")).toBeVisible();
  await add.getByLabel("Name", { exact: true }).fill("Study Leave");
  await add.getByLabel("Days a year", { exact: true }).fill("3.50");
  await add.getByLabel("Carry-over limit (days)", { exact: true }).fill("1.25");
  await add.getByLabel("Accrual method").selectOption("monthly");
  await add.getByLabel("Colour", { exact: true }).selectOption("green");
  await add.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: "Study Leave", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Add leave type" }).click();
  await add.getByLabel("Name", { exact: true }).fill("study leave");
  await add.getByRole("button", { name: "Save", exact: true }).click();
  await expect(add.getByText("You already have a leave type with that name.")).toBeVisible();
  await add.getByRole("button", { name: "Cancel", exact: true }).click();

  await page.getByRole("button", { name: "Study Leave", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "Edit Study Leave" });
  await expect(edit.getByLabel("Accrual method")).toHaveValue("monthly");
  await edit.getByLabel("Name", { exact: true }).fill("Professional Study");
  await edit.getByLabel("Days a year", { exact: true }).fill("");
  await edit.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: "Professional Study", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Professional Study", exact: true }).click();
  const archive = page.getByRole("dialog", { name: "Edit Professional Study" });
  await expect(archive.getByLabel("Days a year", { exact: true })).toHaveValue("");
  await archive.getByRole("button", { name: "Archive", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Archive", exact: true }).click();
  // The table is inert while confirmation is open, so an absent role alone can pass
  // before DELETE finishes. Wait for the success acknowledgement before reloading.
  await expect(page.getByText("Leave type archived", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Professional Study", exact: true })).toHaveCount(
    0,
  );
  await page.reload();
  await expect(page.getByText("12 rows", { exact: true })).toBeVisible();
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280] as const) {
      test(`settings and type sheet at ${width}px pass axe`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        await expect(page.getByRole("heading", { name: "Leave types", exact: true })).toBeVisible();
        // The streamed server copy must be removed before axe checks document-wide ids.
        await expect(page.locator("#leave-types-heading")).toHaveCount(1);
        await audit(page, `${colorScheme} leave settings ${width}px`);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          ),
        ).toBeLessThanOrEqual(0);
        await page.getByRole("button", { name: "Add leave type" }).click();
        await expect(page.getByRole("dialog", { name: "Add leave type" })).toBeVisible();
        await audit(page, `${colorScheme} leave type sheet ${width}px`, { modal: true });
      });
    }
  });
}
