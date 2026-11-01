import { expect, test } from "@playwright/test";

import { nonceOf, parseCsp } from "./helpers";

const PAGES = ["/", "/login", "/dashboard", "/this-page-does-not-exist"];

test.describe("security headers on every page", () => {
  for (const path of PAGES) {
    test(`${path}`, async ({ request }) => {
      const response = await request.get(path);
      const h = response.headers();

      expect(h["strict-transport-security"]).toBe("max-age=63072000; includeSubDomains; preload");
      expect(h["x-content-type-options"]).toBe("nosniff");
      expect(h["x-frame-options"]).toBe("DENY");
      expect(h["referrer-policy"]).toBe("strict-origin-when-cross-origin");
      expect(h["permissions-policy"]).toBe("camera=(), microphone=(), geolocation=()");

      // Nothing identifies the framework or server software.
      expect(h["x-powered-by"]).toBeUndefined();
      expect(h["server"]).toBeUndefined();

      // Pages carry a per-request nonce, so they must never be cached or shared.
      expect(h["cache-control"]).toMatch(/no-store|private/);
    });
  }
});

test.describe("Content-Security-Policy", () => {
  test("is strict", async ({ request }) => {
    const csp = parseCsp((await request.get("/")).headers()["content-security-policy"]);

    expect(csp.get("default-src")).toEqual(["'self'"]);
    expect(csp.get("frame-ancestors")).toEqual(["'none'"]);
    expect(csp.get("object-src")).toEqual(["'none'"]);
    expect(csp.get("base-uri")).toEqual(["'self'"]);
    expect(csp.get("form-action")).toEqual(["'self'"]);
    expect(csp.has("upgrade-insecure-requests")).toBe(true);

    const scripts = csp.get("script-src") ?? [];
    expect(scripts).not.toContain("'unsafe-inline'");
    expect(scripts).not.toContain("'unsafe-eval'");
    expect(scripts).toContain("'strict-dynamic'");
    expect(csp.get("style-src")).not.toContain("'unsafe-inline'");
  });

  test("uses a different nonce for every request", async ({ request }) => {
    const nonces = new Set<string>();
    for (let i = 0; i < 5; i += 1) {
      nonces.add(nonceOf(parseCsp((await request.get("/")).headers()["content-security-policy"])));
    }
    expect(nonces.size).toBe(5);
  });

  test("the nonce in the header is the one on every script tag in the page", async ({
    request,
  }) => {
    const response = await request.get("/");
    const nonce = nonceOf(parseCsp(response.headers()["content-security-policy"]));
    const html = await response.text();

    const scriptTags = html.match(/<script\b[^>]*>/g) ?? [];
    expect(scriptTags.length).toBeGreaterThan(0);
    for (const tag of scriptTags) {
      expect(tag, `script tag without the nonce: ${tag}`).toContain(`nonce="${nonce}"`);
    }
  });

  test("an attacker-supplied nonce or CSP header is not used", async ({ request }) => {
    const response = await request.get("/", {
      headers: { "content-security-policy": "script-src 'nonce-ATTACKER'", "x-nonce": "ATTACKER" },
    });
    const csp = parseCsp(response.headers()["content-security-policy"]);
    expect(nonceOf(csp)).not.toBe("ATTACKER");
    expect(await response.text()).not.toContain("ATTACKER");
  });
});

test.describe("other responses", () => {
  test("static assets get the base headers", async ({ request }) => {
    const page = await (await request.get("/")).text();
    const asset = /\/_next\/static\/[^"']+\.js/.exec(page)?.[0];
    expect(asset).toBeTruthy();

    const response = await request.get(asset ?? "");
    expect(response.status()).toBe(200);
    const h = response.headers();
    expect(h["x-content-type-options"]).toBe("nosniff");
    expect(h["x-frame-options"]).toBe("DENY");
    expect(h["strict-transport-security"]).toContain("includeSubDomains");
    expect(h["x-powered-by"]).toBeUndefined();
  });

  test("the health check answers without caching", async ({ request }) => {
    const response = await request.get("/healthz");
    expect(response.status()).toBe(200);
    expect(await response.text()).toBe("ok");
    expect(response.headers()["cache-control"]).toBe("no-store");
  });

  test("geolocation is allowed only on the opt-in clock-in page", async ({ request }) => {
    const clock = await request.get("/clock");
    expect(clock.headers()["permissions-policy"]).toBe(
      "camera=(), microphone=(), geolocation=(self)",
    );
    const other = await request.get("/clockwork");
    expect(other.headers()["permissions-policy"]).toContain("geolocation=()");
  });
});
