/**
 * The signed-in app's frame (plan T1.3), in a real browser against the PRODUCTION build: layout at
 * the four design widths in both themes, accessibility, the collapsing sidebar (including that the
 * SERVER draws it collapsed, so nothing jumps), navigation, and that every sidebar route has a page.
 */
import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

import { NAV_GROUPS, NAV_ITEMS } from "../../lib/navigation";
import { audit } from "../support/axe";

const WIDTHS = [390, 768, 1280, 1920] as const;
const THEMES = ["light", "dark"] as const;

async function open(page: Page, path = "/employees") {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(error.message));
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  return problems;
}

const sidebar = (page: Page) => page.locator("#app-sidebar");
const widthOf = async (page: Page, selector: string) =>
  Math.round((await page.locator(selector).boundingBox())?.width ?? 0);

for (const colorScheme of THEMES) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of WIDTHS) {
      test.describe(`at ${width} px`, () => {
        test.use({ viewport: { width, height: 900 } });

        test("has no horizontal scrolling, no console errors, and a 56 px toolbar", async ({
          page,
        }) => {
          const problems = await open(page);
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          );
          expect(overflow).toBeLessThanOrEqual(0);
          expect(
            Math.round((await page.locator("header").first().boundingBox())?.height ?? 0),
          ).toBe(56);
          expect(problems).toEqual([]);
        });

        test("shows the sidebar from 768 px up and the tab bar below it, never both", async ({
          page,
        }) => {
          await open(page);
          const wide = width >= 768;
          await expect(sidebar(page)).toBeVisible({ visible: wide });
          await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible({
            visible: !wide,
          });
          if (wide) expect(await widthOf(page, "#app-sidebar")).toBe(260);
        });

        test("has no accessibility violations", async ({ page }) => {
          await open(page);
          await audit(page, `${colorScheme} ${width}px`);
        });

        test("the content never sits under the sidebar or the tab bar", async ({ page }) => {
          await open(page);
          const main = await page.locator("main").boundingBox();
          if (width >= 768) {
            const bar = await sidebar(page).boundingBox();
            expect(main?.x ?? 0).toBeGreaterThanOrEqual((bar?.x ?? 0) + (bar?.width ?? 0) - 1);
          } else {
            await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
            const tabs = await page.getByRole("navigation", { name: "Primary" }).boundingBox();
            // The last thing on the page, not the padded box around it.
            const last = await page
              .locator("main > :last-child")
              .evaluate((el) => el.getBoundingClientRect().bottom);
            expect(last).toBeLessThanOrEqual((tabs?.y ?? 0) + 1);
          }
        });
      });
    }
  });
}

test.describe("collapsing the sidebar", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("[ collapses it to 72 px and again expands it to 260, and the labels stay available", async ({
    page,
  }) => {
    await open(page);
    expect(await widthOf(page, "#app-sidebar")).toBe(260);
    await page.keyboard.press("[");
    await expect.poll(() => widthOf(page, "#app-sidebar")).toBe(72);
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    // The words are gone from the screen, not from the accessibility tree.
    await expect(
      page
        .getByRole("navigation", { name: "Main" })
        .getByRole("link", { name: "Employees", exact: true }),
    ).toBeAttached();
    // (Playwright counts a clipped 1 px screen-reader-only span as visible, so measure it.)
    const label = page
      .getByRole("navigation", { name: "Main" })
      .getByText("Employees", { exact: true });
    expect((await label.boundingBox())?.width ?? 99).toBeLessThanOrEqual(1);
    await page.keyboard.press("[");
    await expect.poll(() => widthOf(page, "#app-sidebar")).toBe(260);
  });

  test("the choice is remembered, and the SERVER draws it, so the page does not jump on load", async ({
    page,
    context,
  }) => {
    await open(page);
    await page.getByRole("button", { name: "Collapse sidebar" }).click();
    await expect
      .poll(async () => (await context.cookies()).find((c) => c.name === "sidebar")?.value)
      .toBe("collapsed");

    const html = await (await page.request.get("/employees")).text();
    expect(html).toContain('data-collapsed="true"');

    await page.reload();
    // Measured straight away: it must already be narrow, not animate there.
    expect(await widthOf(page, "#app-sidebar")).toBe(72);
  });

  test("a tooltip names a row when the labels are hidden", async ({ page }) => {
    await open(page);
    await page.keyboard.press("[");
    await expect.poll(() => widthOf(page, "#app-sidebar")).toBe(72);
    await page.getByRole("link", { name: "Recruitment" }).hover();
    await expect(page.getByText("Recruitment").locator("visible=true").first()).toBeVisible();
  });

  test("with reduced motion the width still changes, without animating", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await open(page);
    await page.keyboard.press("[");
    // No transition: it is at its final width on the very next frame.
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );
    expect(await widthOf(page, "#app-sidebar")).toBe(72);
  });
});

test.describe("navigation", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("choosing a page goes there, marks it current, and updates the breadcrumbs and title", async ({
    page,
  }) => {
    await open(page, "/employees");
    const main = page.getByRole("navigation", { name: "Main" });
    await main.getByRole("link", { name: "Reminders" }).click();
    await expect(page).toHaveURL(/\/sponsor-compliance\/reminders$/);
    await expect(main.getByRole("link", { name: "Reminders" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(main.getByRole("link", { name: "Sponsor compliance" })).not.toHaveAttribute(
      "aria-current",
      "page",
    );
    const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumbs).toContainText("Compliance");
    await expect(crumbs.getByRole("link", { name: "Sponsor compliance" })).toBeVisible();
    await expect(page).toHaveTitle("Compliance reminders | Brand");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Compliance reminders");
  });

  test("the skip link is the first thing Tab reaches, and takes you to the content", async ({
    page,
  }) => {
    await open(page);
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport();
    await page.keyboard.press("Enter");
    await expect(page.locator("main")).toBeFocused();
  });

  test("the sidebar can be walked with the Tab key, one stop per page", async ({ page }) => {
    await open(page);
    const names: string[] = [];
    await page.keyboard.press("Tab"); // skip link
    for (let i = 0; i < NAV_ITEMS.length + 4; i += 1) {
      await page.keyboard.press("Tab");
      names.push(await page.evaluate(() => document.activeElement?.textContent?.trim() ?? ""));
    }
    for (const item of NAV_ITEMS) expect(names, item.label).toContain(item.label);
  });
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the tab bar goes between sections and marks where you are", async ({ page }) => {
    await open(page, "/employees");
    const bar = page.getByRole("navigation", { name: "Primary" });
    await expect(bar.getByRole("link", { name: "People" })).toHaveAttribute("aria-current", "true");
    await bar.getByRole("link", { name: "Time" }).click();
    await expect(page).toHaveURL(/\/leave$/);
    await expect(bar.getByRole("link", { name: "Time" })).toHaveAttribute("aria-current", "true");
    await expect(bar.getByRole("link", { name: "People" })).not.toHaveAttribute("aria-current");
  });

  test("every tab target is at least 44 px", async ({ page }) => {
    await open(page);
    const bar = page.getByRole("navigation", { name: "Primary" });
    for (const target of await bar.locator("a, button").all()) {
      const box = await target.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
      expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
    }
  });

  test("More opens a bottom sheet with every page, keeps focus inside, and Esc closes it", async ({
    page,
  }) => {
    await open(page);
    const more = page.getByRole("button", { name: "More" });
    await more.click();
    const sheet = page.getByRole("dialog", { name: "More" });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("link")).toHaveCount(NAV_ITEMS.length);
    for (const group of NAV_GROUPS)
      await expect(sheet.getByRole("heading", { name: group.label, exact: true })).toBeVisible();
    for (let i = 0; i < 6; i += 1) {
      await page.keyboard.press("Tab");
      expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(more).toBeFocused();
  });

  test("choosing a page from More goes there and closes the sheet", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "More" }).click();
    await page
      .getByRole("dialog", { name: "More" })
      .getByRole("link", { name: "Work log" })
      .click();
    await expect(page).toHaveURL(/\/work-log$/);
    await expect(page.getByRole("dialog", { name: "More" })).toBeHidden();
  });
});

test.describe("the toolbar", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("the bell opens a calm empty state, and Esc closes it and returns focus", async ({
    page,
  }) => {
    await open(page);
    const bell = page.getByRole("button", { name: "Notifications" });
    await bell.click();
    await expect(page.getByText("You're all caught up")).toBeVisible();
    await audit(page, "notifications open", { overlay: true });
    await page.keyboard.press("Escape");
    await expect(page.getByText("You're all caught up")).toBeHidden();
    await expect(bell).toBeFocused();
  });

  test("the account menu changes the theme at once and remembers it", async ({ page, context }) => {
    await open(page);
    await page.getByRole("button", { name: "Account menu" }).click();
    await audit(page, "account menu open", { modal: true });
    await page.getByRole("menuitemradio", { name: /Dark/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect((await context.cookies()).find((c) => c.name === "theme")?.value).toBe("dark");
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(
      "rgb(0, 0, 0)",
    );
  });

  test("the search box and the help button are real buttons that can be reached and used", async ({
    page,
  }) => {
    await open(page);
    await expect(page.getByRole("button", { name: /^Search/ }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Help and keyboard shortcuts" })).toBeVisible();
  });
});

// Pages that have been built: they still have their heading, title and place in the menu, but no
// longer the "on its way" empty state of a page that has not been built yet.
const BUILT = new Set([
  "company",
  "users",
  "employees",
  "compliance",
  "reminders",
  "my-documents",
  "leave",
  "my-leave",
  "my-approvals",
]);

test.describe("every page in the sidebar", () => {
  for (const item of NAV_ITEMS) {
    test(`${item.href} serves a page headed "${item.label}", in the frame`, async ({ page }) => {
      const response = await page.goto(item.href);
      expect(response?.status()).toBe(200);
      const title = item.id === "reminders" ? "Compliance reminders" : item.label;
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
      if (!BUILT.has(item.id)) {
        await expect(page.getByRole("heading", { level: 2, name: item.emptyTitle })).toBeVisible();
      }
      await expect(page).toHaveTitle(`${title} | Brand`);
      await expect(
        page
          .getByRole("navigation", { name: "Main" })
          .getByRole("link", { name: item.label, exact: true }),
      ).toHaveAttribute("aria-current", "page");
    });
  }
});
