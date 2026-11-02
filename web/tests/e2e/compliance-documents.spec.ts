/**
 * Compliance documents (plan T4.4), against the real API and a real signed-in Company Admin: all 18
 * are listed, the sheet asks for a document before it saves, and the page passes axe in both themes.
 * (Uploading goes through the file store and the virus scanner, which the API tests cover.)
 */
import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

import { audit } from "../support/axe";

async function open(page: Page) {
  await page.goto("/company/compliance-documents");
  await expect(page.getByRole("heading", { level: 1, name: "Compliance documents" })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("all 18 documents are listed as missing, and a save needs a document", async ({ page }) => {
  await open(page);
  await expect(page.getByText("0 of 18 held")).toBeVisible();
  const rows = page.getByRole("region", { name: "Documents" }).getByRole("button");
  await expect(rows).toHaveCount(18);
  await expect(rows.first()).toContainText("PAYE and Accounts Office reference letter from HMRC");
  await expect(rows.first()).toContainText("Missing");
  await expect(rows.last()).toContainText("Other");

  await rows.nth(2).click();
  const sheet = page.getByRole("dialog", { name: "Employer's liability insurance certificate" });
  await expect(sheet.getByText("Not added yet.")).toBeVisible();
  await sheet.getByRole("button", { name: "Save", exact: true }).click();
  await expect(sheet.getByText("Choose the document to add.")).toBeVisible();
  await sheet.getByRole("button", { name: "Cancel" }).click();

  await page.goto("/company");
  await expect(page.getByRole("link", { name: /^Compliance documents/ })).toContainText("0 of 18");
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of [390, 1280] as const) {
      test(`the page at ${width} px passes axe, and so does the sheet`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await audit(page, `${colorScheme} compliance documents ${width}px`);
        await page.getByRole("region", { name: "Documents" }).getByRole("button").first().click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await page.waitForTimeout(500);
        await audit(page, `${colorScheme} compliance document sheet ${width}px`, { modal: true });
      });
    }
  });
}
