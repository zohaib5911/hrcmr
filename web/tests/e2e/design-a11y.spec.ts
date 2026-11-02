/**
 * Accessibility of every component on /design (plan T1.2: "axe shows 0 serious issues"). It is
 * stricter than that: ZERO violations at any severity, against WCAG 2.2 AA and axe's best practices,
 * in both themes, at desktop and phone width, and with each overlay OPEN (dialogs, menus and the
 * calendar are drawn outside the page, so a scan of the page alone never sees them).
 */
import { expect, test } from "@playwright/test";

import { audit } from "../support/axe";
import { openDesign } from "../support/design-page";

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test("the whole page, at desktop width", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await openDesign(page);
      await audit(page, "page");
    });

    test("the whole page, at phone width (tables become cards)", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openDesign(page);
      await expect(page.locator('ul[aria-label="Employees"]')).toBeVisible();
      await audit(page, "phone");
    });

    test("the whole page with reduced motion", async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await openDesign(page);
      await audit(page, "reduced motion");
    });

    test("a dialog, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Open a dialog" }).click();
      await expect(page.getByRole("dialog", { name: "Add a location" })).toBeVisible();
      await audit(page, "dialog", { modal: true });
    });

    test("the inspector sheet, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Open the inspector" }).click();
      await expect(page.getByRole("dialog", { name: "Ada Lovelace" })).toBeVisible();
      await audit(page, "sheet", { modal: true });
    });

    test("a dialog as a bottom sheet on a phone", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openDesign(page);
      await page.getByRole("button", { name: "Open a dialog" }).click();
      await expect(page.getByRole("dialog", { name: "Add a location" })).toBeVisible();
      await audit(page, "dialog on phone", { modal: true });
    });

    test("the confirmation that asks for a name", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Delete permanently" }).click();
      await expect(page.getByRole("alertdialog")).toBeVisible();
      await audit(page, "confirm dialog", { modal: true });
    });

    test("a menu, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Actions", exact: true }).click();
      await expect(page.getByRole("menu")).toBeVisible();
      await audit(page, "menu", { modal: true });
    });

    test("a popover, open", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Open a popover" }).click();
      await expect(page.getByText("Why a 14-day wait?")).toBeVisible();
      await audit(page, "popover", { overlay: true });
    });

    test("the calendar, open", async ({ page }) => {
      await openDesign(page);
      await page.locator("#inputs").getByLabel("Start date", { exact: true }).first().focus();
      await page.keyboard.press("Alt+ArrowDown");
      await expect(
        page.getByRole("dialog", { name: "Choose start date" }).getByRole("grid"),
      ).toBeVisible();
      await audit(page, "calendar", { overlay: true });
    });

    test("a combobox list, open", async ({ page }) => {
      await openDesign(page);
      await page.locator('#inputs input[role="combobox"]').first().fill("e");
      await expect(page.getByRole("listbox")).toBeVisible();
      await audit(page, "combobox", { overlay: true });
    });

    test("a toast, showing", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("button", { name: "Success with Undo" }).click();
      await expect(page.getByText("Leave approved").first()).toBeVisible();
      await audit(page, "toast", { overlay: true });
    });

    test("a tooltip, showing", async ({ page }) => {
      await openDesign(page);
      const button = page.getByRole("button", { name: "Hover or focus me" });
      // Scroll first: Radix closes a tooltip on any scroll, and focus() on an off-screen button scrolls.
      await button.scrollIntoViewIfNeeded();
      // A focus that arrives before the page has hydrated is missed, so focus again until it shows.
      await expect(async () => {
        await button.blur();
        await button.focus();
        await expect(page.getByText("Shown on hover and on keyboard focus").first()).toBeVisible({
          timeout: 1000,
        });
      }).toPass({ timeout: 10_000 });
      await audit(page, "tooltip", { overlay: true });
    });
  });
}
