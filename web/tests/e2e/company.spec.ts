/**
 * The company overview and its details sheet (plan T4.1), against the real API and a real signed-in
 * Company Admin: the page at the four design widths in both themes passes axe, the sheet passes axe,
 * and a save changes what the page shows. (The logo upload needs the file store and the virus scanner,
 * which the API tests cover.)
 */
import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

import { audit } from "../support/axe";

const WIDTHS = [390, 768, 1280, 1920] as const;

async function open(page: Page) {
  await page.goto("/company");
  await expect(page.getByRole("heading", { level: 1, name: "Company" })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of WIDTHS) {
      test(`the overview at ${width} px has no sideways scroll and passes axe`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        await expect(page.getByRole("region", { name: "Your company" })).toBeVisible();
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await audit(page, `${colorScheme} company ${width}px`);
      });
    }

    for (const width of [390, 1280] as const) {
      test(`the details sheet at ${width} px passes axe`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        await page.getByRole("button", { name: /^Details/ }).click();
        await expect(page.getByRole("dialog", { name: "Company details" })).toBeVisible();
        await audit(page, `${colorScheme} company details ${width}px`, { modal: true });
      });
    }
  });
}

test("the card, the groups and the counts are there, and the lookup is off without a key", async ({
  page,
}) => {
  await open(page);
  await expect(page.getByRole("region", { name: "Your company" })).toContainText(
    "Harbourside Care",
  );
  await expect(page.getByRole("region", { name: "Your company" })).toContainText("Free plan");
  await expect(page.getByRole("main").getByRole("link", { name: /User access/ })).toContainText(
    "1 person",
  );
  await expect(page.getByRole("main").getByRole("link", { name: /Billing/ })).toContainText(
    "Free plan",
  );
  await page.getByRole("button", { name: /^Details/ }).click();
  const sheet = page.getByRole("dialog", { name: "Company details" });
  await expect(sheet.getByRole("button", { name: "Look up" })).toHaveCount(0);
  await expect(sheet.getByText("AI features")).toHaveCount(0);
});

test("a save shows on the page, a wrong value is explained, and Cancel changes nothing", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("button", { name: /^Details/ }).click();
  const sheet = page.getByRole("dialog", { name: "Company details" });

  await sheet.getByLabel("Trading name", { exact: true }).fill("Harbourside");
  await sheet.getByLabel("Website", { exact: true }).fill("example.com");
  await sheet.getByRole("button", { name: "Save" }).click();
  await expect(
    sheet.getByText("Enter a web address starting with https:// or http://"),
  ).toBeVisible();

  await sheet.getByLabel("Website", { exact: true }).fill("https://example.com");
  await sheet
    .getByLabel("Legal structure", { exact: true })
    .selectOption("private_limited_by_shares");
  await sheet.getByRole("radio", { name: "Yes" }).first().click();
  await sheet.getByLabel("Previous company name", { exact: true }).fill("Harbour Care");
  await sheet.getByRole("button", { name: "Save" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByText("Company details saved")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Details/ })).toContainText("Harbourside");

  await page.reload();
  await page.getByRole("button", { name: /^Details/ }).click();
  const again = page.getByRole("dialog", { name: "Company details" });
  await expect(again.getByLabel("Website", { exact: true })).toHaveValue("https://example.com");
  await expect(again.getByLabel("Previous company name", { exact: true })).toHaveValue(
    "Harbour Care",
  );
  await again.getByLabel("Trading name", { exact: true }).fill("Changed but cancelled");
  await again.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: /^Details/ })).toContainText("Harbourside");
  await expect(page.getByRole("button", { name: /^Details/ })).not.toContainText("cancelled");
});
