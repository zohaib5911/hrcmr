import { describe, expect, it, vi } from "vitest";

import {
  hasPlatformCookie,
  PLATFORM_COOKIE,
  refusalMessage,
  safeNextPath,
  startPlatformSession,
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

describe("startPlatformSession", () => {
  it("forwards the cookies and the CSRF token, and returns the Set-Cookie headers on 201", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(null, {
          status: 201,
          headers: { "set-cookie": `${PLATFORM_COOKIE}=abc; Path=/; HttpOnly` },
        }),
    ) as unknown as typeof fetch;
    const outcome = await startPlatformSession({
      apiBase: "https://api.example.com/api/v1",
      cookieHeader: "brand_session=s1; csrf=t1",
      csrfToken: "t1",
      fetchImpl,
    });
    expect(outcome.ok).toBe(true);
    if (outcome.ok) expect(outcome.setCookies.join(";")).toContain(`${PLATFORM_COOKIE}=abc`);
    const [url, init] = vi.mocked(fetchImpl).mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.example.com/api/v1/auth/platform-session");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      cookie: "brand_session=s1; csrf=t1",
      "X-CSRF-Token": "t1",
    });
  });

  it("returns the API's error code on a refusal", async () => {
    const fetchImpl = (async () =>
      new Response(JSON.stringify({ error: { code: "MFA_ENROLMENT_REQUIRED" } }), {
        status: 403,
      })) as unknown as typeof fetch;
    const outcome = await startPlatformSession({
      apiBase: "https://api.example.com/api/v1",
      cookieHeader: "",
      fetchImpl,
    });
    expect(outcome).toEqual({ ok: false, code: "MFA_ENROLMENT_REQUIRED" });
  });

  it("says the server is unreachable when the call fails", async () => {
    const fetchImpl = (async () => {
      throw new TypeError("fetch failed");
    }) as unknown as typeof fetch;
    const outcome = await startPlatformSession({
      apiBase: "https://api.example.com/api/v1",
      cookieHeader: "",
      fetchImpl,
    });
    expect(outcome).toEqual({ ok: false, code: "UNREACHABLE" });
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
