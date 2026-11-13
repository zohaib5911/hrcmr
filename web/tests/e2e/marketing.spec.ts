/**
 * The public website's frame (plan T1.5), in a real browser against the production build: the home
 * page at the four design widths in both themes (no sideways scroll, axe clean), the mobile menu, the
 * FAQ, and the cookie banner and preferences (only necessary cookies until the visitor chooses).
 */
import { expect, test, type Page } from "@playwright/test";

import { expectBrandLogo } from "../support/brand";

import { audit } from "../support/axe";

const WIDTHS = [390, 768, 1280, 1920] as const;
const consentOf = (page: Page) =>
  page.evaluate(() => window.localStorage.getItem("brand.cookieConsent"));

async function open(page: Page) {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // The cookie component reads the stored choice once React has taken over the page.
  await page.locator('[data-consent-state]:not([data-consent-state="loading"])').waitFor({
    state: "attached",
  });
  return problems;
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of WIDTHS) {
      test(`the home page at ${width} px has no sideways scroll, no errors, and passes axe`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 900 });
        const problems = await open(page);
        await expectBrandLogo(page.locator("header").first(), colorScheme);
        await expectBrandLogo(page.locator("footer").last(), colorScheme);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await expect(page.getByRole("region", { name: "Cookies" })).toBeVisible();
        await audit(page, `${colorScheme} home ${width}px`);
        expect(problems).toEqual([]);
      });
    }
  });
}

test.describe("the header and footer", () => {
  test("a desktop header has the links; a phone's menu opens a sheet that closes with Esc", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await open(page);
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Menu" })).toBeHidden();

    await page.setViewportSize({ width: 390, height: 800 });
    await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
    const menu = page.getByRole("button", { name: "Menu" });
    await menu.click();
    const sheet = page.getByRole("dialog", { name: "Menu" });
    await expect(sheet.getByRole("link", { name: "Pricing" })).toBeVisible();
    await audit(page, "mobile menu open", { modal: true });
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(menu).toBeFocused();
  });

  test("the footer has four columns of links and a Cookie settings link", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await open(page);
    const footer = page.getByRole("contentinfo");
    for (const title of ["Product", "Resources", "Company", "Legal"]) {
      await expect(footer.getByRole("navigation", { name: title })).toBeVisible();
    }
    await expect(footer.getByRole("button", { name: "Cookie settings" })).toBeVisible();
  });

  test("the header stays on screen when the page is scrolled", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 600 });
    await open(page);
    await page.evaluate(() => window.scrollTo(0, 800));
    await expect(page.getByRole("banner")).toBeInViewport();
  });
});

test.describe("the FAQ", () => {
  test("opens one answer at a time from the keyboard", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await open(page);
    const first = page.getByRole("button", { name: /Do I need a sponsor licence/ });
    const second = page.getByRole("button", { name: /Does it give legal advice/ });
    await first.focus();
    await page.keyboard.press("Enter");
    await expect(first).toHaveAttribute("aria-expanded", "true");
    await second.focus();
    await page.keyboard.press("Space");
    await expect(second).toHaveAttribute("aria-expanded", "true");
    await expect(first).toHaveAttribute("aria-expanded", "false");
  });
});

test.describe("cookies", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("nothing is stored until the visitor chooses, and Reject is as easy as Accept", async ({
    page,
  }) => {
    await open(page);
    const banner = page.getByRole("region", { name: "Cookies" });
    await expect(banner).toBeVisible();
    expect(await consentOf(page)).toBeNull();
    await banner.getByRole("button", { name: "Reject all" }).click();
    await expect(banner).toBeHidden();
    const saved = JSON.parse((await consentOf(page)) ?? "null");
    expect(saved).toMatchObject({ version: 1, marketing: false });
    expect(typeof saved.decidedAt).toBe("string");

    await page.reload();
    await expect(page.locator('[data-consent-state="decided"]')).toBeAttached();
    await expect(banner).toBeHidden();
  });

  test("Choose opens the preferences, which pass axe and save the marketing switch", async ({
    page,
  }) => {
    await open(page);
    await page
      .getByRole("region", { name: "Cookies" })
      .getByRole("button", { name: "Choose" })
      .click();
    const dialog = page.getByRole("dialog", { name: "Cookie settings" });
    await expect(dialog).toBeVisible();
    await audit(page, "cookie settings open", { modal: true });
    await dialog.getByRole("switch", { name: "Marketing" }).click();
    await dialog.getByRole("button", { name: "Save choices" }).click();
    await expect(dialog).toBeHidden();
    expect(JSON.parse((await consentOf(page)) ?? "null")).toMatchObject({ marketing: true });
  });

  test("the footer link reopens the preferences with the saved choice", async ({ page }) => {
    await open(page);
    await page
      .getByRole("region", { name: "Cookies" })
      .getByRole("button", { name: "Accept all" })
      .click();
    await page.getByRole("button", { name: "Cookie settings" }).click();
    const dialog = page.getByRole("dialog", { name: "Cookie settings" });
    await expect(dialog.getByRole("switch", { name: "Marketing" })).toBeChecked();
  });
});
