import { describe, expect, it } from "vitest";

import { DEFAULT_ACCENT, brandAccentCss } from "./brand-style";

describe("brandAccentCss", () => {
  it("emits nothing for the default accent, so the stylesheet's own values apply", () => {
    expect(brandAccentCss({ accent: DEFAULT_ACCENT.light, accentDark: DEFAULT_ACCENT.dark })).toBe(
      "",
    );
  });

  it("overrides ONLY accent tokens, in every way a theme can be chosen", () => {
    const css = brandAccentCss({ accent: "#7A3E00", accentDark: "#FFB066" });
    const names = new Set([...css.matchAll(/(--[a-z-]+):/g)].map((m) => m[1]));
    expect([...names].sort()).toEqual(["--accent", "--accent-pressed", "--accent-text"]);
    expect(css).toContain(':root,[data-theme="light"]{');
    expect(css).toContain("@media (prefers-color-scheme:dark){:root:not([data-theme]){");
    expect(css).toContain('[data-theme="dark"]{');
    expect(css).toContain("--accent:#7A3E00");
    expect(css).toContain("--accent:#FFB066");
  });

  it("only ever writes validated hex colours, so config can never inject CSS", () => {
    for (const bad of ["red", "#12", "#GGGGGG", "#000000;}body{display:none", "url(x)", ""]) {
      expect(() => brandAccentCss({ accent: bad, accentDark: DEFAULT_ACCENT.dark })).toThrow(
        /#rrggbb/,
      );
      expect(() => brandAccentCss({ accent: DEFAULT_ACCENT.light, accentDark: bad })).toThrow(
        /#rrggbb/,
      );
    }
  });

  it("refuses a light accent that makes white button text unreadable", () => {
    expect(() => brandAccentCss({ accent: "#FFD60A", accentDark: DEFAULT_ACCENT.dark })).toThrow(
      /white text/i,
    );
  });

  it("refuses a light accent whose link text fails on its own tint, even though white text passes", () => {
    // White on #BB00FF is 4.6:1, but the link colour on a 12% tint of it is 4.4:1 (tinted buttons).
    expect(() => brandAccentCss({ accent: "#BB00FF", accentDark: DEFAULT_ACCENT.dark })).toThrow(
      /own tint/,
    );
  });

  it("refuses a dark accent that is too dim for black button text or for links on cards", () => {
    expect(() => brandAccentCss({ accent: DEFAULT_ACCENT.light, accentDark: "#1A3A66" })).toThrow(
      /AA/,
    );
  });
});
