/**
 * Search and keyboard shortcuts (plan T1.4 and 8.19), in a real browser against the production build:
 * every shortcut that works anywhere does its job, the shortcuts sheet lists all of them, and the
 * palette and the sheet pass the accessibility check in both themes.
 *
 * The row shortcuts (J, K, Enter, Space, ".") and "/" need a table and a list search, which the
 * placeholder pages do not have yet; they are covered by data-table.test.tsx and
 * shortcut-provider.test.tsx, and in a browser by design-components.spec.ts.
 */
import { expect, test, type Page } from "@playwright/test";

import { GO_TARGETS, SHORTCUT_GROUPS } from "../../lib/shortcuts";
import { audit } from "../support/axe";

test.use({ viewport: { width: 1280, height: 900 } });

async function open(page: Page, path = "/employees") {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // The shortcuts are listening once the page has hydrated.
  await page.waitForLoadState("networkidle");
}

const palette = (page: Page) => page.getByRole("combobox", { name: "Search pages" });
const sheet = (page: Page) => page.getByRole("dialog", { name: "Keyboard shortcuts" });

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test("the palette opens with Ctrl+K, finds a page, opens it, and passes axe", async ({
      page,
    }) => {
      await open(page);
      await page.keyboard.press("Control+k");
      await expect(palette(page)).toBeFocused();
      await audit(page, `${colorScheme} palette open`, { modal: true });
      await page.keyboard.type("leave");
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/\/leave$/);
      await expect(palette(page)).toBeHidden();
    });

    test("? opens the sheet, which lists every shortcut and passes axe; Esc closes it", async ({
      page,
    }) => {
      await open(page);
      await page.keyboard.press("?");
      await expect(sheet(page)).toBeVisible();
      await audit(page, `${colorScheme} shortcuts sheet open`, { modal: true });
      for (const group of SHORTCUT_GROUPS) {
        for (const shortcut of group.shortcuts) {
          await expect(sheet(page).getByText(shortcut.label, { exact: true })).toBeVisible();
        }
      }
      await page.keyboard.press("Escape");
      await expect(sheet(page)).toBeHidden();
    });
  });
}

test("G then a letter goes to each page it is listed for", async ({ page }) => {
  await open(page, "/dashboard");
  for (const [letter, target] of Object.entries(GO_TARGETS)) {
    await page.keyboard.press("g");
    await page.keyboard.press(letter);
    await expect(page).toHaveURL(new RegExp(`${target.href}$`));
  }
});

test("[ collapses and expands the sidebar, and typing in the palette does not trigger shortcuts", async ({
  page,
}) => {
  await open(page);
  const sidebar = page.locator("#app-sidebar");
  const wide = (await sidebar.boundingBox())?.width ?? 0;
  await page.keyboard.press("[");
  await expect.poll(async () => (await sidebar.boundingBox())?.width ?? wide).toBeLessThan(wide);
  await page.keyboard.press("[");
  await expect.poll(async () => (await sidebar.boundingBox())?.width ?? 0).toBe(wide);

  await page.keyboard.press("Control+k");
  await page.keyboard.type("g?[n");
  await expect(palette(page)).toHaveValue("g?[n");
  await expect(sheet(page)).toBeHidden();
});
