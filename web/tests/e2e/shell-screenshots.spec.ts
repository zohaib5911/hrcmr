/**
 * Design QA screenshots of the app shell (plan 5.12 and T1.3): four widths in light and dark, plus
 * the collapsed sidebar and the phone "More" sheet; and (T1.4, T1.5) the search palette, the shortcuts
 * sheet, and the public home page with its menu and cookie banner. They are the evidence kept in
 * docs/screenshots/phase-1/, so this runs only when asked, and normal test runs never rewrite them:
 *
 *   SCREENSHOTS=1 pnpm exec playwright test shell-screenshots --project=production
 */
import path from "node:path";

import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-1");
const WIDTHS = [390, 768, 1280, 1920] as const;

test.skip(!process.env.SCREENSHOTS, "Screenshots are only taken on request (SCREENSHOTS=1).");

async function ready(page: Page, route: string) {
  await page.goto(route);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  // Let the page settle: no hover, no transition in flight.
  await page.mouse.move(0, 0);
  await page.waitForTimeout(400);
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });

    for (const width of WIDTHS) {
      test(`shell at ${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
        await ready(page, "/sponsor-compliance/reminders");
        await page.screenshot({ path: path.join(OUT, `shell-${colorScheme}-${width}.png`) });
      });
    }

    test("shell with the sidebar collapsed", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await ready(page, "/employees");
      await page.keyboard.press("[");
      await expect
        .poll(async () =>
          Math.round((await page.locator("#app-sidebar").boundingBox())?.width ?? 0),
        )
        .toBe(72);
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(OUT, `shell-${colorScheme}-collapsed.png`) });
    });

    test("phone More sheet", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await ready(page, "/employees");
      await page.getByRole("button", { name: "More" }).click();
      await expect(page.getByRole("dialog", { name: "More" })).toBeVisible();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(OUT, `shell-${colorScheme}-more-sheet.png`) });
    });
  });
}

const CHOSEN = JSON.stringify({
  version: 1,
  marketing: false,
  decidedAt: "2026-11-02T10:00:00.000Z",
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme}: search, shortcuts and the public site`, () => {
    test.use({ colorScheme });

    test("search palette and shortcuts sheet", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await ready(page, "/employees");
      await page.keyboard.press("Control+k");
      await page.keyboard.type("lea");
      await expect(page.getByRole("combobox", { name: "Search pages" })).toBeFocused();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(OUT, `palette-${colorScheme}-1280.png`) });
      await page.keyboard.press("Escape");
      await expect(page.getByRole("combobox", { name: "Search pages" })).toBeHidden();
      await page.keyboard.press("?");
      await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(OUT, `shortcuts-${colorScheme}-1280.png`) });
    });

    test("phone palette", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await ready(page, "/employees");
      await page.getByRole("button", { name: "Search" }).first().click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(OUT, `palette-${colorScheme}-390.png`) });
    });

    for (const width of WIDTHS) {
      test(`public home at ${width}`, async ({ page }) => {
        await page.addInitScript((value) => {
          window.localStorage.setItem("brand.cookieConsent", value);
        }, CHOSEN);
        await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
        await ready(page, "/");
        await page.screenshot({
          path: path.join(OUT, `public-home-${colorScheme}-${width}.png`),
          fullPage: true,
        });
      });
    }

    for (const width of [390, 1280] as const) {
      test(`public home with the cookie banner at ${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
        await ready(page, "/");
        await expect(page.getByRole("region", { name: "Cookies" })).toBeVisible();
        await page.screenshot({
          path: path.join(OUT, `public-cookies-${colorScheme}-${width}.png`),
        });
      });
    }

    test("cookie preferences", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await ready(page, "/");
      await page.getByRole("button", { name: "Choose" }).click();
      await expect(page.getByRole("dialog", { name: "Cookie settings" })).toBeVisible();
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(OUT, `public-cookie-settings-${colorScheme}-1280.png`),
      });
    });

    test("phone menu", async ({ page }) => {
      await page.addInitScript((value) => {
        window.localStorage.setItem("brand.cookieConsent", value);
      }, CHOSEN);
      await page.setViewportSize({ width: 390, height: 844 });
      await ready(page, "/");
      await page.getByRole("button", { name: "Menu" }).click();
      await expect(page.getByRole("dialog", { name: "Menu" })).toBeVisible();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(OUT, `public-menu-${colorScheme}-390.png`) });
    });
  });
}
