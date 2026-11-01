import { describe, expect, it } from "vitest";

import { SIDEBAR_COOKIE, isEditableTarget, parseSidebar, sidebarCookie } from "./sidebar";

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

describe("isEditableTarget", () => {
  it("is true for text boxes, areas, selects and editable regions, and false for everything else", () => {
    for (const tagName of ["INPUT", "TEXTAREA", "SELECT"])
      expect(isEditableTarget({ tagName })).toBe(true);
    expect(isEditableTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
    expect(isEditableTarget({ tagName: "BUTTON" })).toBe(false);
    expect(isEditableTarget({ tagName: "BODY" })).toBe(false);
    expect(isEditableTarget(null)).toBe(false);
    expect(isEditableTarget(undefined)).toBe(false);
  });
});
