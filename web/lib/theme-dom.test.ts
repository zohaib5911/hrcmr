import { describe, expect, it } from "vitest";

import { applyTheme, type ThemeTarget } from "./theme-dom";

function fakeDocument() {
  const attributes = new Map<string, string>();
  const target: ThemeTarget = {
    cookie: "",
    documentElement: {
      setAttribute: (name: string, value: string) => void attributes.set(name, value),
      removeAttribute: (name: string) => void attributes.delete(name),
    },
  };
  return { target, attributes };
}

describe("applyTheme", () => {
  it("saves an explicit choice and stamps it on <html>", () => {
    const { target, attributes } = fakeDocument();
    applyTheme("dark", target, true);
    expect(target.cookie).toMatch(/^theme=dark;/);
    expect(attributes.get("data-theme")).toBe("dark");
  });

  it("returns to the system setting by removing both the cookie and the attribute", () => {
    const { target, attributes } = fakeDocument();
    applyTheme("light", target, false);
    applyTheme("system", target, false);
    expect(target.cookie).toMatch(/^theme=;.*Max-Age=0/);
    expect(attributes.has("data-theme")).toBe(false);
  });
});
