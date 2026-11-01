import { describe, expect, it } from "vitest";

import { THEME_COOKIE, parseTheme, themeAttribute, themeCookie } from "./theme";

describe("parseTheme", () => {
  it("accepts the three choices", () => {
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme("system")).toBe("system");
  });

  it("falls back to the system setting for anything else, so a tampered cookie changes nothing", () => {
    for (const value of [undefined, null, "", "DARK", "blue", "dark; Path=/", '"><script>', "0"]) {
      expect(parseTheme(value)).toBe("system");
    }
  });
});

describe("themeAttribute", () => {
  it("stamps data-theme only for an explicit choice", () => {
    expect(themeAttribute("light")).toBe("light");
    expect(themeAttribute("dark")).toBe("dark");
    expect(themeAttribute("system")).toBeUndefined();
  });
});

describe("themeCookie", () => {
  it("stores an explicit choice for a year, for this site only, never readable cross-site", () => {
    const cookie = themeCookie("dark", true);
    expect(cookie).toContain(`${THEME_COOKIE}=dark`);
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("Max-Age=31536000");
    expect(cookie).toContain("SameSite=Lax");
    expect(cookie).toContain("Secure");
  });

  it("omits Secure on plain http (local development) so the cookie can be set at all", () => {
    expect(themeCookie("light", false)).not.toContain("Secure");
  });

  it("expires the cookie when the user goes back to following the system", () => {
    const cookie = themeCookie("system", true);
    expect(cookie).toContain(`${THEME_COOKIE}=;`);
    expect(cookie).toContain("Max-Age=0");
  });
});
