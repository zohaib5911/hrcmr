/**
 * Guards globals.css against the design plan (section 5) and against itself:
 *   - every colour, shadow, type style, radius and duration equals the plan's number;
 *   - light and dark define the same tokens, and the two ways of choosing dark are identical;
 *   - every colour pair that carries text or an interface control meets WCAG AA in both themes.
 * Break any value in the stylesheet and one of these fails.
 */
import { describe, expect, it } from "vitest";

import {
  CONTRAST_PAIRS,
  ELEVATIONS,
  MARKETING_STYLES,
  RADII,
  THEME_TOKEN_NAMES,
  TYPE_STYLES,
} from "../../../lib/design/catalog";
import { contrastRatio } from "../../../lib/design/contrast";
import { DURATION } from "../../../lib/motion";
import { DEVIATIONS, EXPECTED_DARK, EXPECTED_LIGHT } from "../../support/expected-tokens";
import {
  GLOBALS_CSS,
  LIGHT_BLOCK,
  EXPLICIT_DARK_BLOCK,
  blockBody,
  declarations,
  normalise,
  themeBlocks,
  visibleColour,
} from "../support/css";

const { light, systemDark, explicitDark } = themeBlocks();

describe("colour tokens match the plan", () => {
  it.each(Object.entries(EXPECTED_LIGHT))("light %s", (name, value) => {
    expect(light.get(name), name).toBeDefined();
    expect(normalise(light.get(name) ?? ""), name).toBe(normalise(value));
  });

  it.each(Object.entries(EXPECTED_DARK))("dark %s", (name, value) => {
    expect(explicitDark.get(name), name).toBeDefined();
    expect(normalise(explicitDark.get(name) ?? ""), name).toBe(normalise(value));
  });

  it("changes a plan value only where the plan fails its own AA rule (and says so)", () => {
    expect(Object.keys(DEVIATIONS.light).sort()).toEqual([
      "--danger",
      "--info",
      "--success",
      "--warning",
    ]);
    expect(Object.keys(DEVIATIONS.dark)).toEqual(["--danger"]);
  });
});

describe("themes agree with each other", () => {
  it("define exactly the tokens in the catalog, no more and no fewer", () => {
    const wanted = [...THEME_TOKEN_NAMES].sort();
    expect([...light.keys()].sort()).toEqual(wanted);
    expect([...explicitDark.keys()].sort()).toEqual(wanted);
  });

  it("choose dark identically from the system setting and from data-theme=dark", () => {
    expect([...systemDark.entries()].sort()).toEqual([...explicitDark.entries()].sort());
  });

  it("tell the browser which colour scheme each theme is, for form controls and scrollbars", () => {
    expect(blockBody(GLOBALS_CSS, LIGHT_BLOCK)).toMatch(/color-scheme:\s*light;/);
    expect(blockBody(GLOBALS_CSS, EXPLICIT_DARK_BLOCK)).toMatch(/color-scheme:\s*dark;/);
  });
});

describe("WCAG AA (plan 5.3)", () => {
  const themes = [
    ["light", light],
    ["dark", explicitDark],
  ] as const;

  it("checks the pairs that matter", () => {
    const foregrounds = new Set(CONTRAST_PAIRS.map((pair) => pair.fg));
    for (const name of [
      "--label",
      "--label-secondary",
      "--label-tertiary",
      "--accent-text",
      "--accent",
      "--on-accent",
      "--success",
      "--warning",
      "--danger",
      "--info",
    ]) {
      expect(foregrounds.has(name), `${name} has no contrast pair`).toBe(true);
    }
    expect(CONTRAST_PAIRS.length).toBeGreaterThanOrEqual(40);
  });

  for (const [theme, tokens] of themes) {
    it.each(
      CONTRAST_PAIRS.map(
        (pair) =>
          [`${pair.fg} on ${pair.bg}${pair.over ? ` over ${pair.over}` : ""}`, pair] as const,
      ),
    )(`${theme}: %s`, (_label, pair) => {
      const fg = visibleColour(pair.fg, tokens);
      const bg = visibleColour(pair.bg, tokens, pair.over);
      expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(pair.min);
    });
  }
});

// ---- Typography (plan 5.2) ---------------------------------------------------------------------

const theme = declarations(blockBody(GLOBALS_CSS, /@theme\s*\{/));
const rem = (value: string | undefined) => Number.parseFloat(value ?? "NaN") * 16;

describe("type scale", () => {
  it.each(TYPE_STYLES.map((style) => [style.label, style] as const))("%s", (_label, style) => {
    const key = `--text-${style.key}`;
    expect(rem(theme.get(key)), `${key} size`).toBeCloseTo(style.size, 5);
    expect(rem(theme.get(`${key}--line-height`)), `${key} line height`).toBeCloseTo(
      style.lineHeight,
      5,
    );
    expect(Number(theme.get(`${key}--font-weight`)), `${key} weight`).toBe(style.weight);
    const trackingEm = Number.parseFloat(theme.get(`${key}--letter-spacing`) ?? "NaN");
    expect(trackingEm * style.size, `${key} tracking`).toBeCloseTo(style.tracking, 1);
  });

  it("keeps body text at 15/22 and never below the plan's smallest size", () => {
    expect(Math.min(...TYPE_STYLES.map((style) => style.size))).toBe(11);
    expect(TYPE_STYLES.find((style) => style.key === "body")).toMatchObject({
      size: 15,
      lineHeight: 22,
    });
  });
});

describe("marketing type scale", () => {
  const pxAt = (value: string, width: number) => {
    const parts = /^clamp\(([\d.]+)rem,\s*([\d.]+)rem \+ ([\d.]+)vw,\s*([\d.]+)rem\)$/.exec(
      value.trim(),
    );
    if (!parts) throw new Error(`Not a clamp() of the expected shape: ${value}`);
    const [, floor, base, slope, ceiling] = parts.map(Number);
    return {
      floor: (floor ?? 0) * 16,
      ceiling: (ceiling ?? 0) * 16,
      at: Math.min(
        Math.max((base ?? 0) * 16 + ((slope ?? 0) * width) / 100, (floor ?? 0) * 16),
        (ceiling ?? 0) * 16,
      ),
    };
  };

  it.each(MARKETING_STYLES.map((style) => [style.label, style] as const))("%s", (_label, style) => {
    const value = theme.get(`--text-${style.key}`);
    expect(value, "missing").toBeDefined();
    const small = pxAt(value ?? "", 1024);
    const large = pxAt(value ?? "", 1440);
    expect(small.at).toBeCloseTo(style.desktopMin, 0);
    expect(large.at).toBeCloseTo(style.desktopMax, 0);
    expect(small.floor).toBe(style.floor);
    expect(pxAt(value ?? "", 390).at).toBe(style.floor);
  });

  it("sets the hero at line height 1.05, weight 700, tracking -0.03em", () => {
    expect(theme.get("--text-hero--line-height")).toBe("1.05");
    expect(theme.get("--text-hero--font-weight")).toBe("700");
    expect(theme.get("--text-hero--letter-spacing")).toBe("-0.03em");
  });

  it("sets marketing body text at line height 1.5", () => {
    expect(theme.get("--text-lead--line-height")).toBe("1.5");
  });
});

describe("font stack (plan 5.2)", () => {
  it("puts the system UI font first, then self-hosted Inter (with safe fallbacks if its variable is missing), then common fallbacks", () => {
    expect(normalise(theme.get("--font-sans") ?? "")).toBe(
      normalise(
        '-apple-system, BlinkMacSystemFont, var(--font-inter, "Inter var"), var(--font-inter-ext, "Inter"), system-ui, "Segoe UI", Roboto, sans-serif',
      ),
    );
  });
});

// ---- Shape, space and motion (plan 5.4, 5.5) -----------------------------------------------------

describe("radius", () => {
  it.each(RADII.map((radius) => [radius.key, radius] as const))("%s", (_key, radius) => {
    expect(theme.get(`--radius-${radius.key}`)).toBe(`${radius.px}px`);
  });
});

describe("layout widths and elevations", () => {
  it("uses a 1200 px app width and a 1120 px marketing text width", () => {
    expect(rem(theme.get("--container-app"))).toBe(1200);
    expect(rem(theme.get("--container-marketing"))).toBe(1120);
  });

  it("has three elevations, each defined for both themes", () => {
    expect(ELEVATIONS.map((e) => e.name)).toEqual(["--e1", "--e2", "--e3"]);
    for (const { name } of ELEVATIONS) {
      expect(light.has(name)).toBe(true);
      expect(explicitDark.has(name)).toBe(true);
    }
  });
});

describe("motion durations in CSS match the TypeScript presets", () => {
  const root = declarations(blockBody(GLOBALS_CSS, /:root\s*\{\s*--duration-micro/));
  it("micro, small and sheet", () => {
    expect(root.get("--duration-micro")).toBe(`${DURATION.micro * 1000}ms`);
    expect(root.get("--duration-small")).toBe(`${DURATION.small * 1000}ms`);
    expect(root.get("--duration-sheet")).toBe(`${DURATION.sheet * 1000}ms`);
  });
});
