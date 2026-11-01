import { describe, expect, it } from "vitest";

import {
  composite,
  contrastRatio,
  formatColour,
  mixSrgb,
  parseColour,
  parseComputedColour,
  toHex,
} from "./contrast";

const ratio = (a: string, b: string) => contrastRatio(parseColour(a), parseColour(b));

describe("parseColour", () => {
  it("reads hex in both lengths", () => {
    expect(parseColour("#fff")).toEqual({ r: 255, g: 255, b: 255, a: 1 });
    expect(parseColour("#1D1D1F")).toEqual({ r: 29, g: 29, b: 31, a: 1 });
  });

  it("reads rgb() and rgba() with commas or spaces", () => {
    expect(parseColour("rgba(120, 120, 128, 0.12)")).toEqual({ r: 120, g: 120, b: 128, a: 0.12 });
    expect(parseColour("rgb(1 2 3)")).toEqual({ r: 1, g: 2, b: 3, a: 1 });
  });

  it("rejects anything it cannot read instead of guessing", () => {
    expect(() => parseColour("oklch(0.5 0.1 200)")).toThrow(/Unsupported colour/);
    expect(() => parseColour("#12345")).toThrow(/Unsupported colour/);
    expect(() => parseColour("rgb(a, b, c)")).toThrow(/Unsupported colour/);
  });
});

describe("contrastRatio", () => {
  // Reference values published with the WCAG definition and by independent checkers.
  it("is 21:1 for black on white and 1:1 for identical colours", () => {
    expect(ratio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(ratio("#336699", "#336699")).toBeCloseTo(1, 5);
  });

  it("is symmetric", () => {
    expect(ratio("#0071E3", "#F5F5F7")).toBeCloseTo(ratio("#F5F5F7", "#0071E3"), 10);
  });

  it("matches a known mid-grey: #767676 on white is 4.54:1", () => {
    expect(ratio("#767676", "#ffffff")).toBeCloseTo(4.54, 2);
  });
});

describe("composite and mixSrgb", () => {
  it("lays a translucent colour over an opaque one", () => {
    const over = composite(parseColour("rgba(0, 0, 0, 0.5)"), parseColour("#ffffff"));
    expect(toHex(over)).toBe("#808080");
  });

  it("mixes in sRGB like color-mix(in srgb, a 88%, b)", () => {
    const mixed = mixSrgb(parseColour("#0071E3"), parseColour("#000000"), 0.88);
    expect(toHex(mixed)).toBe("#0063C8");
  });
});

describe("parseComputedColour", () => {
  it("reads what Chrome reports for plain and translucent colours", () => {
    expect(parseComputedColour("rgb(245, 245, 247)")).toEqual({ r: 245, g: 245, b: 247, a: 1 });
    expect(parseComputedColour("rgba(120, 120, 128, 0.12)")).toEqual({
      r: 120,
      g: 120,
      b: 128,
      a: 0.12,
    });
  });

  it("reads colour-mix() results, which arrive as color(srgb ...) with components from 0 to 1", () => {
    const colour = parseComputedColour("color(srgb 0.2 0.78 0.35 / 0.12)");
    expect(colour.r).toBeCloseTo(51, 5);
    expect(colour.g).toBeCloseTo(198.9, 5);
    expect(colour.a).toBe(0.12);
  });

  it("refuses colour spaces it cannot judge", () => {
    expect(() => parseComputedColour("oklch(0.5 0.1 200)")).toThrow(/Cannot read/);
  });
});

describe("formatColour", () => {
  it("writes opaque colours as #RRGGBB and translucent ones as rgba(), like the plan's table", () => {
    expect(formatColour({ r: 245, g: 245, b: 247, a: 1 })).toBe("#F5F5F7");
    expect(formatColour({ r: 120, g: 120, b: 128, a: 0.12 })).toBe("rgba(120, 120, 128, 0.12)");
    expect(formatColour({ r: 50.6, g: 198.9, b: 89.2, a: 0.1200001 })).toBe(
      "rgba(51, 199, 89, 0.12)",
    );
  });
});
