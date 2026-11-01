/**
 * The /design page against a development server (plan.md T1.1). It checks what a visitor SEES, using
 * the browser's own computed styles, not the stylesheet text (tests/unit/design/tokens.test.ts does
 * that): every token in both themes, the type scale, real contrast ratios, theme switching and
 * reduced motion.
 */
import { expect, test, type Page } from "@playwright/test";

import {
  COLOUR_TOKENS,
  CONTRAST_PAIRS,
  ELEVATIONS,
  MARKETING_STYLES,
  TYPE_STYLES,
} from "../../lib/design/catalog";
import { composite, contrastRatio, parseComputedColour } from "../../lib/design/contrast";
import { EXPECTED_DARK, EXPECTED_LIGHT } from "../support/expected-tokens";
import { resolveColour } from "../support/colour";

const THEMES = [
  { theme: "light", expected: EXPECTED_LIGHT },
  { theme: "dark", expected: EXPECTED_DARK },
] as const;

const themeSwitch = (page: Page) => page.getByRole("group", { name: "Colour theme" });

const px = (value: string) => (value === "normal" ? 0 : Number.parseFloat(value));

async function openDesign(page: Page) {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  await page.goto("/design");
  await expect(page.getByRole("heading", { level: 1, name: "Design tokens" })).toBeVisible();
  // Hydration has run once every live token value has been read from the browser.
  await expect(page.locator('[data-token-value="--bg"]').first()).not.toHaveText("…");
  return problems;
}

test.describe("every token, in both themes", () => {
  test("the page loads cleanly and fetches nothing from outside this site", async ({ page }) => {
    const external: string[] = [];
    page.on("request", (request) => {
      const { protocol, hostname } = new URL(request.url());
      if (protocol.startsWith("http") && hostname !== "localhost") external.push(request.url());
    });
    const problems = await openDesign(page);
    await page.evaluate(() => document.fonts.ready);
    expect(problems).toEqual([]);
    expect(external).toEqual([]);
  });

  for (const { theme, expected } of THEMES) {
    test(`${theme}: each colour token is painted with the plan's colour`, async ({ page }) => {
      await openDesign(page);
      const panel = page.getByTestId(`panel-${theme}`);
      const swatches = await panel.locator("[data-swatch]").evaluateAll((elements) =>
        elements.map((element) => ({
          name: element.getAttribute("data-swatch") ?? "",
          colour: getComputedStyle(element).backgroundColor,
        })),
      );
      // Nothing missing and nothing extra (the page groups swatches by category, so order differs).
      expect(swatches.map((swatch) => swatch.name).sort()).toEqual(
        COLOUR_TOKENS.map((token) => token.name).sort(),
      );

      const tokens = new Map(Object.entries(expected));
      for (const { name, colour } of swatches) {
        const want = resolveColour(name, tokens);
        const got = parseComputedColour(colour);
        for (const channel of ["r", "g", "b"] as const) {
          expect(
            Math.abs(got[channel] - want[channel]),
            `${theme} ${name} ${channel}`,
          ).toBeLessThan(1.01);
        }
        expect(Math.abs(got.a - want.a), `${theme} ${name} alpha`).toBeLessThan(0.006);
      }
    });

    test(`${theme}: each elevation shows a shadow, or a hairline border in dark`, async ({
      page,
    }) => {
      await openDesign(page);
      const panel = page.getByTestId(`panel-${theme}`);
      for (const { name } of ELEVATIONS) {
        const shadow = await panel
          .locator(`[data-elevation="${name}"]`)
          .evaluate((element) => getComputedStyle(element).boxShadow);
        if (theme === "dark") expect(shadow, name).toContain("rgba(255, 255, 255, 0.08)");
        else expect(shadow, name).toContain("rgba(0, 0, 0,");
      }
    });

    test(`${theme}: the values shown are the colours the browser resolved`, async ({ page }) => {
      await openDesign(page);
      const panel = page.getByTestId(`panel-${theme}`);
      const shown = (token: string) => panel.locator(`[data-token-value="${token}"]`);
      await expect(panel.locator("[data-token-value]")).toHaveCount(COLOUR_TOKENS.length);
      await expect(shown("--bg")).toHaveText(theme === "light" ? "#F5F5F7" : "#000000");
      await expect(shown("--fill-secondary")).toHaveText(
        theme === "light" ? "rgba(120, 120, 128, 0.12)" : "rgba(120, 120, 128, 0.24)",
      );
      // A derived token shows its real result, not the formula.
      await expect(shown("--accent-text")).toHaveText(theme === "light" ? "#0063C8" : "#2997FF");
    });

    test(`${theme}: every text and control pair meets WCAG AA as the browser resolves it`, async ({
      page,
    }) => {
      await openDesign(page);
      const resolved = await page.evaluate(
        ({ testId, pairs }) => {
          const panel = document.querySelector(`[data-testid="${testId}"]`);
          if (!panel) throw new Error("panel not found");
          const paint = (property: "color" | "backgroundColor", token: string) => {
            const probe = document.createElement("div");
            probe.style[property] = `var(${token})`;
            panel.append(probe);
            const value = getComputedStyle(probe)[property];
            probe.remove();
            return value;
          };
          return pairs.map((pair) => ({
            pair,
            fg: paint("color", pair.fg),
            bg: paint("backgroundColor", pair.bg),
            over: pair.over ? paint("backgroundColor", pair.over) : null,
          }));
        },
        { testId: `panel-${theme}`, pairs: [...CONTRAST_PAIRS] },
      );

      expect(resolved.length).toBe(CONTRAST_PAIRS.length);
      for (const { pair, fg, bg, over } of resolved) {
        const background = parseComputedColour(bg);
        const visible =
          background.a < 1 && over ? composite(background, parseComputedColour(over)) : background;
        const ratio = contrastRatio(composite(parseComputedColour(fg), visible), visible);
        expect(
          ratio,
          `${theme}: ${pair.fg} on ${pair.bg}${pair.over ? ` over ${pair.over}` : ""}`,
        ).toBeGreaterThanOrEqual(pair.min);
      }
    });
  }
});

test.describe("typography", () => {
  test("every app text style has the plan's size, line height, weight and tracking", async ({
    page,
  }) => {
    await openDesign(page);
    for (const style of TYPE_STYLES) {
      const sample = page.locator(`[data-type-style="${style.key}"] p`).last();
      const computed = await sample.evaluate((element) => {
        const css = getComputedStyle(element);
        return {
          size: css.fontSize,
          line: css.lineHeight,
          weight: css.fontWeight,
          tracking: css.letterSpacing,
        };
      });
      expect(px(computed.size), `${style.key} size`).toBeCloseTo(style.size, 1);
      expect(px(computed.line), `${style.key} line height`).toBeCloseTo(style.lineHeight, 1);
      expect(Number(computed.weight), `${style.key} weight`).toBe(style.weight);
      expect(px(computed.tracking), `${style.key} tracking`).toBeCloseTo(style.tracking, 1);
    }
  });

  test("marketing text scales between the plan's sizes and shrinks on phones", async ({ page }) => {
    await openDesign(page);
    const sizeOf = (key: string) =>
      page
        .locator(`[data-type-style="${key}"] p`)
        .last()
        .evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize));

    for (const style of MARKETING_STYLES) {
      await page.setViewportSize({ width: 1024, height: 800 });
      expect(await sizeOf(style.key), `${style.key} at 1024`).toBeCloseTo(style.desktopMin, 0);
      await page.setViewportSize({ width: 1440, height: 900 });
      expect(await sizeOf(style.key), `${style.key} at 1440`).toBeCloseTo(style.desktopMax, 0);
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await sizeOf(style.key), `${style.key} at 390`).toBe(style.floor);
    }
  });

  test("Inter is self-hosted and in use", async ({ page }) => {
    await openDesign(page);
    await page.evaluate(() => document.fonts.ready);
    const loaded = await page.evaluate(() =>
      [...document.fonts].filter((face) => face.status === "loaded").map((face) => face.family),
    );
    expect(loaded.some((family) => /inter/i.test(family))).toBe(true);
    const stack = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(stack).toMatch(/-apple-system/);
    expect(stack).toMatch(/BlinkMacSystemFont/);
  });

  test("numbers in tables use tabular figures", async ({ page }) => {
    await openDesign(page);
    const value = await page.evaluate(() => {
      const table = document.createElement("table");
      document.body.append(table);
      const result = getComputedStyle(table).fontVariantNumeric;
      table.remove();
      return result;
    });
    expect(value).toContain("tabular-nums");
  });
});

test.describe("choosing a theme", () => {
  const rootState = (page: Page) =>
    page.evaluate(() => ({
      attribute: document.documentElement.getAttribute("data-theme"),
      background: getComputedStyle(document.body).backgroundColor,
      scheme: getComputedStyle(document.documentElement).colorScheme,
    }));

  test.describe("the system is dark", () => {
    test.use({ colorScheme: "dark" });

    test("with no choice the page follows it", async ({ page }) => {
      await openDesign(page);
      expect(await rootState(page)).toEqual({
        attribute: null,
        background: "rgb(0, 0, 0)",
        scheme: "dark",
      });
    });

    test("an explicit light choice wins, and the server renders it with no flash", async ({
      page,
      context,
    }) => {
      await context.addCookies([{ name: "theme", value: "light", url: "http://localhost:3101" }]);
      const html = await (await page.request.get("/design")).text();
      expect(html).toMatch(/<html[^>]*data-theme="light"/);
      await openDesign(page);
      expect(await rootState(page)).toEqual({
        attribute: "light",
        background: "rgb(245, 245, 247)",
        scheme: "light",
      });
    });
  });

  test.describe("the system is light", () => {
    test.use({ colorScheme: "light" });

    test("an explicit dark choice wins", async ({ page, context }) => {
      await context.addCookies([{ name: "theme", value: "dark", url: "http://localhost:3101" }]);
      await openDesign(page);
      expect(await rootState(page)).toMatchObject({
        attribute: "dark",
        background: "rgb(0, 0, 0)",
      });
    });

    test("a tampered cookie is ignored", async ({ page, context }) => {
      await context.addCookies([
        { name: "theme", value: "%22%3E%3Cscript%3E", url: "http://localhost:3101" },
      ]);
      await openDesign(page);
      expect((await rootState(page)).attribute).toBeNull();
    });

    test("the switch applies at once, is remembered, and System undoes it", async ({
      page,
      context,
    }) => {
      await openDesign(page);
      const cookie = async () => (await context.cookies()).find((c) => c.name === "theme")?.value;

      await themeSwitch(page).getByText("Dark", { exact: true }).click();
      await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
      expect(await rootState(page)).toMatchObject({
        attribute: "dark",
        background: "rgb(0, 0, 0)",
      });
      expect(await cookie()).toBe("dark");

      // Remembered: a fresh request is already dark in the HTML the server sends.
      const html = await (await page.request.get("/design")).text();
      expect(html).toMatch(/<html[^>]*data-theme="dark"/);
      await page.reload();
      await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();

      await themeSwitch(page).getByText("System", { exact: true }).click();
      expect(await cookie()).toBeUndefined();
      expect((await rootState(page)).attribute).toBeNull();
    });

    test("the switch can be used with the keyboard", async ({ page }) => {
      await openDesign(page);
      await page.getByRole("radio", { name: "System" }).focus();
      await page.keyboard.press("ArrowRight"); // Light
      await page.keyboard.press("ArrowRight"); // Dark
      await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
      expect((await rootState(page)).attribute).toBe("dark");
    });
  });
});

test.describe("motion", () => {
  test.describe("by default", () => {
    test("things travel 8 px when they enter", async ({ page }) => {
      await openDesign(page);
      const distance = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue("--motion-distance").trim(),
      );
      expect(distance).toBe("8px");
    });
  });

  test.describe("when the user prefers reduced motion", () => {
    test.use({ reducedMotion: "reduce" });

    test("nothing travels", async ({ page }) => {
      await openDesign(page);
      const distance = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue("--motion-distance").trim(),
      );
      expect(distance).toBe("0px");
    });
  });
});

test.describe("responsive", () => {
  for (const width of [360, 390, 768, 1280, 1920]) {
    test(`no horizontal scrolling at ${width} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await openDesign(page);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});
