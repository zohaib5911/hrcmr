import { describe, expect, it } from "vitest";

import {
  hasPlatformCookie,
  PLATFORM_COOKIE,
  refusalMessage,
  safeNextPath,
  toPublicPath,
} from "./session";

describe("toPublicPath", () => {
  it("maps the internal admin segment back to the public path", () => {
    expect(toPublicPath("/platform/rules")).toBe("/rules");
    expect(toPublicPath("/platform")).toBe("/");
    expect(toPublicPath("/platform/")).toBe("/");
    expect(toPublicPath("/session")).toBe("/session");
  });
});

describe("safeNextPath", () => {
  it("keeps a plain path on this admin host", () => {
    expect(safeNextPath("/rules")).toBe("/rules");
    expect(safeNextPath("/courses/new")).toBe("/courses/new");
  });

  it("falls back to the home path for anything that could leave the host or reach the segment", () => {
    for (const raw of [
      null,
      "",
      "rules",
      "//evil.example",
      "https://evil.example",
      "/\\evil",
      "/platform/rules",
      "/a\nb",
    ]) {
      expect(safeNextPath(raw)).toBe("/");
    }
  });
});

describe("refusalMessage and hasPlatformCookie", () => {
  it("tells the person what to do for each refusal, and never shows a raw code", () => {
    expect(refusalMessage("MFA_ENROLMENT_REQUIRED")).toContain("two-step verification");
    expect(refusalMessage("MFA_REQUIRED")).toContain("authenticator");
    expect(refusalMessage("WHATEVER")).not.toContain("WHATEVER");
  });

  it("finds the platform cookie among the names", () => {
    expect(hasPlatformCookie(["csrf", PLATFORM_COOKIE])).toBe(true);
    expect(hasPlatformCookie(["csrf", "brand_session"])).toBe(false);
  });
});
