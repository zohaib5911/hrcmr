import { describe, expect, it, vi } from "vitest";

const incoming = vi.hoisted(() => ({
  headers: new Headers(),
  cookie: "brand_platform_session=test",
}));
vi.mock("next/headers", () => ({
  cookies: async () => ({ has: () => true, toString: () => incoming.cookie }),
  headers: async () => incoming.headers,
}));
vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    throw new Error(`REDIRECT ${to}`);
  },
}));

import { dataOrSessionRedirect, platformApi, sessionStartPath } from "./guard";

describe("dataOrSessionRedirect", () => {
  it("returns the data on success", () => {
    expect(dataOrSessionRedirect({ data: { a: 1 }, response: { status: 200 } }, "/")).toEqual({
      a: 1,
    });
  });
  it("returns null on another failure", () => {
    expect(dataOrSessionRedirect({ response: { status: 500 } }, "/")).toBeNull();
  });
  it.each([401, 403])("sends a %i to the start page", (status) => {
    expect(() => dataOrSessionRedirect({ response: { status } }, "/companies")).toThrow(
      "REDIRECT /session?next=%2Fcompanies",
    );
  });
  it("builds the start path", () => {
    expect(sessionStartPath("/")).toBe("/session?next=%2F");
  });
});

describe("platformApi", () => {
  it("fails closed when ingress identity or signing configuration is missing", async () => {
    expect(await platformApi()).toBeNull();
  });
  it("signs the real SSR request without relaying untrusted forwarding headers", async () => {
    vi.stubEnv("PLATFORM_INGRESS_SECRET", "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii");
    vi.stubEnv("PLATFORM_SSR_SECRET", "ssssssssssssssssssssssssssssssss");
    vi.stubEnv("API_INTERNAL_URL", "http://api.internal/api/v1");
    incoming.headers = new Headers({
      "x-platform-ingress-key": process.env.PLATFORM_INGRESS_SECRET!,
      "x-platform-visitor-ip": "203.0.113.7",
      "user-agent": "Admin browser",
      "x-forwarded-for": "attacker",
    });
    const fetch = vi.fn(
      async (request: Request) =>
        new Response(JSON.stringify({ url: request.url }), {
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetch);
    try {
      const client = await platformApi();
      await client!.GET("/platform/metrics");
      const request = fetch.mock.calls[0]![0] as unknown as Request;
      expect(request.headers.get("cookie")).toBe(incoming.cookie);
      expect(request.headers.get("x-forwarded-for")).toBeNull();
      expect(request.headers.get("x-platform-ingress-key")).toBeNull();
      expect(request.headers.get("x-platform-signature")).toMatch(/^[a-f0-9]{64}$/);
    } finally {
      vi.unstubAllGlobals();
      vi.unstubAllEnvs();
    }
  });
});
