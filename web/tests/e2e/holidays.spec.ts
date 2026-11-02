/**
 * The working pattern and the holiday pages (plan T4.5), against the real API and a real signed-in
 * Company Admin. GOV.UK's bank holidays arrive by the weekly job (covered by the API tests), so here
 * the list is empty and the page says so; the pattern, closures and types are used for real.
 */
import { expect, test, type Page } from "@playwright/test";

import { audit } from "../support/axe";

test.describe.configure({ mode: "serial" });

async function open(page: Page, path: string, heading: string) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("the working pattern starts as Monday to Friday and saves a change", async ({ page }) => {
  await open(page, "/company/working-pattern", "Working pattern");
  await expect(page.getByText("Mon to Fri, 40 hours")).toBeVisible();
  await page.getByRole("switch", { name: "Friday" }).click();
  await page.getByLabel("Wednesday hours", { exact: true }).fill("6");
  await page.getByRole("switch", { name: /Bank holidays are not working days/ }).click();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Working pattern saved").first()).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Working pattern" })).toBeVisible();
  await expect(page.getByText("Mon to Thu, 30 hours")).toBeVisible();
  await expect(page.getByRole("switch", { name: "Friday" })).not.toBeChecked();
  await expect(
    page.getByRole("switch", { name: /Bank holidays are not working days/ }),
  ).not.toBeChecked();
});

test("trading hours start unset and each row saves by itself", async ({ page }) => {
  await open(page, "/company/trading-hours", "Trading hours");
  await expect(page.getByText("Not set yet")).toBeVisible();
  await page.getByRole("switch", { name: "Monday" }).click();
  await expect(page.getByText("Saved").first()).toBeVisible();
  const closes = page.getByLabel("Monday closes", { exact: true });
  await closes.fill("5:30pm");
  await closes.blur();
  await expect(page.getByText("Saved").first()).toBeVisible();
  await page.getByLabel("Monday opens", { exact: true }).fill("18:00");
  await page.getByLabel("Monday opens", { exact: true }).blur();
  await expect(page.getByText("It must open before it closes.")).toBeVisible();
  await page.getByLabel("Monday opens", { exact: true }).fill("08:30");
  await page.getByLabel("Monday opens", { exact: true }).blur();
  await expect(page.getByText("Saved").first()).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Monday opens", { exact: true })).toHaveValue("08:30");
  await expect(page.getByLabel("Monday closes", { exact: true })).toHaveValue("17:30");
  await expect(page.getByText("Open 1 day a week")).toBeVisible();
  await audit(page, "trading hours");
});

test("holiday types and closures: add, use, and a used type cannot be archived", async ({
  page,
}) => {
  await open(page, "/holiday-management?year=2026", "Holidays");
  await expect(page.getByText("they have not been loaded yet", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Add type" }).first().click();
  const typeSheet = page.getByRole("dialog", { name: "Add holiday type" });
  await typeSheet.getByLabel("Name", { exact: true }).fill("Shutdown");
  await typeSheet.getByRole("radio", { name: "Orange" }).click();
  await typeSheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("button", { name: /^Shutdown/ })).toBeVisible();

  await page.getByRole("button", { name: "Add closure" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Add closure" });
  await sheet.getByLabel("Name", { exact: true }).fill("Christmas shutdown");
  await sheet.getByLabel("First day", { exact: true }).fill("24 Dec 2026");
  await sheet.getByLabel("Last day", { exact: true }).fill("2 Jan 2027");
  await sheet.getByLabel("Type (optional)", { exact: true }).selectOption({ label: "Shutdown" });
  await sheet.getByRole("switch", { name: /Take these days from annual leave/ }).click();
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  const row = page.getByRole("button", { name: /Christmas shutdown/ });
  await expect(row).toContainText("24 Dec 2026 to 2 Jan 2027");

  // It also shows in the next year, which it runs into.
  await page.getByRole("button", { name: "Next year" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Holidays" })).toBeVisible();
  await expect(page.getByText("2027", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Christmas shutdown/ })).toBeVisible();

  await page.getByRole("button", { name: /^Shutdown/ }).click();
  await page
    .getByRole("dialog", { name: "Edit holiday type" })
    .getByRole("button", { name: "Archive" })
    .click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Archive" }).click();
  await expect(
    page.getByText("Change or remove the closures that use this type first."),
  ).toBeVisible();
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const [path, heading] of [
      ["/company/working-pattern", "Working pattern"],
      ["/holiday-management?year=2026", "Holidays"],
    ] as const) {
      for (const width of [390, 1280] as const) {
        test(`${heading} at ${width} px passes axe`, async ({ page }) => {
          await page.setViewportSize({ width, height: 900 });
          await open(page, path, heading);
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          );
          expect(overflow).toBeLessThanOrEqual(0);
          await audit(page, `${colorScheme} ${heading} ${width}px`);
        });
      }
    }

    test("the closure sheet passes axe", async ({ page }) => {
      await open(page, "/holiday-management?year=2026", "Holidays");
      await page.getByRole("button", { name: "Add closure" }).first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.waitForTimeout(500);
      await audit(page, `${colorScheme} closure sheet`, { modal: true });
    });
  });
}
