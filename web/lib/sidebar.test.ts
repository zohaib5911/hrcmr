import { describe, expect, it } from "vitest";

import {
  SIDEBAR_COOKIE,
  isEditableTarget,
  parseSidebar,
  sidebarCookie,
  wantsToggle,
} from "./sidebar";

describe("parseSidebar", () => {
  it("is collapsed only when it says so; anything else is expanded", () => {
    expect(parseSidebar("collapsed")).toBe("collapsed");
    expect(parseSidebar("expanded")).toBe("expanded");
    for (const value of [undefined, null, "", "COLLAPSED", "yes", "1", "collapsed; Path=/"]) {
      expect(parseSidebar(value), String(value)).toBe("expanded");
    }
  });
});

describe("sidebarCookie", () => {
  it("is remembered for a year, for this site only", () => {
    const cookie = sidebarCookie("collapsed", true);
    expect(cookie).toContain(`${SIDEBAR_COOKIE}=collapsed`);
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("Max-Age=31536000");
    expect(cookie).toContain("SameSite=Lax");
    expect(cookie).toContain("Secure");
  });

  it("is not marked Secure on plain http (local development), or it could not be saved at all", () => {
    expect(sidebarCookie("expanded", false)).not.toContain("Secure");
  });
});

describe("the [ key (plan 8.19: collapse sidebar)", () => {
  const key = (
    init: Partial<{
      key: string;
      ctrlKey: boolean;
      metaKey: boolean;
      altKey: boolean;
      repeat: boolean;
    }> & { target?: unknown },
  ) =>
    ({
      key: "[",
      ctrlKey: false,
      metaKey: false,
      altKey: false,
      repeat: false,
      target: null,
      ...init,
    }) as Parameters<typeof wantsToggle>[0];

  it("toggles on a bare [", () => {
    expect(wantsToggle(key({}))).toBe(true);
  });

  it("ignores every other key and any shortcut that merely contains it", () => {
    expect(wantsToggle(key({ key: "]" }))).toBe(false);
    expect(wantsToggle(key({ ctrlKey: true }))).toBe(false);
    expect(wantsToggle(key({ metaKey: true }))).toBe(false);
    expect(wantsToggle(key({ altKey: true }))).toBe(false);
  });

  it("does not repeat while the key is held", () => {
    expect(wantsToggle(key({ repeat: true }))).toBe(false);
  });

  it("does nothing while the person is typing", () => {
    for (const tag of ["input", "textarea", "select"]) {
      expect(
        wantsToggle(key({ target: { tagName: tag.toUpperCase(), isContentEditable: false } })),
      ).toBe(false);
    }
    expect(wantsToggle(key({ target: { tagName: "DIV", isContentEditable: true } }))).toBe(false);
    expect(isEditableTarget({ tagName: "BUTTON", isContentEditable: false })).toBe(false);
  });
});
