import { expect, test } from "@playwright/test";

import { ADMIN_HOST, BASE_URL, MAIN_HOST, headingOf } from "./helpers";

const main = { host: MAIN_HOST };
const admin = { host: ADMIN_HOST };

// The public home page's heading (app/(marketing)/page.tsx).
const HOME_HEADING = "Look after your people, and your licence.";

test.describe("main host", () => {
  test("serves the public site and the app", async ({ request }) => {
    expect(await headingOf(await request.get("/", { headers: main }))).toBe(HOME_HEADING);
    expect(await headingOf(await request.get("/login", { headers: main }))).toBe("Sign in");
    expect(await headingOf(await request.get("/dashboard", { headers: main }))).toBe("Dashboard");
  });

  test("the admin pages do not exist", async ({ request }) => {
    for (const path of ["/platform", "/platform/companies"]) {
      const response = await request.get(path, { headers: main });
      expect(response.status(), path).toBe(404);
      expect(await headingOf(response), path).toBe("Page not found");
    }
  });

  test("they cannot be reached with an encoded, re-cased or dotted path", async ({ request }) => {
    const attempts = [
      "/Platform",
      "/PLATFORM",
      "/%70latform",
      "/%50latform",
      "/%2570latform",
      "/platform%2f",
      "/platform%00",
      "/x/%2e%2e/platform",
      "/platform;x",
      "/platform?x=1",
    ];
    for (const path of attempts) {
      const response = await request.get(path, { headers: main, maxRedirects: 0 });
      expect(await headingOf(response), path).not.toBe("Platform admin");
      expect([308, 404], path).toContain(response.status());
    }
  });
});

test.describe("admin host", () => {
  test("sends the back office root to start a platform session first", async ({ request }) => {
    // Owner answer 5 (T17.1): a platform admin's pages need the platform cookie, so the frame sends
    // a visitor without one to /session, which starts it (or explains why it cannot).
    const response = await request.get("/", { headers: admin, maxRedirects: 0 });
    expect(response.status()).toBe(307);
    expect(response.headers()["location"]).toBe("/session?next=%2F");
  });

  test("a visitor without a platform session sees the refusal page on the admin host", async ({
    request,
  }) => {
    const response = await request.get("/", { headers: admin });
    expect(response.status()).toBe(200);
    // The redirect must stay on the host the browser asked for, never the server's bind address.
    expect(new URL(response.url()).origin).toBe(new URL(BASE_URL).origin);
    expect(await headingOf(response)).toBe("Platform session not started");
  });

  test("is kept out of search engines", async ({ request }) => {
    const response = await request.get("/", { headers: admin });
    expect(response.headers()["x-robots-tag"]).toBe("noindex, nofollow");
    const publicSite = await request.get("/", { headers: main });
    expect(publicSite.headers()["x-robots-tag"]).toBeUndefined();
  });

  test("serves nothing from the public site or the company app", async ({ request }) => {
    for (const path of ["/login", "/dashboard", "/pricing"]) {
      const response = await request.get(path, { headers: admin });
      expect(response.status(), path).toBe(404);
      expect(await headingOf(response), path).toBe("Page not found");
    }
  });

  test("the internal /platform path is not reachable directly", async ({ request }) => {
    for (const path of ["/platform", "/platform/x", "/%70latform"]) {
      const response = await request.get(path, { headers: admin });
      expect(response.status(), path).toBe(404);
    }
  });

  test("an encoded path cannot climb out of the admin segment", async ({ request }) => {
    for (const path of ["/%2e%2e/login", "/a/%2e%2e/%2e%2e/login", "/..%2flogin", "//login"]) {
      // An absolute URL, so that "//login" is sent as a path rather than parsed as a host.
      const response = await request.get(`${BASE_URL}${path}`, { headers: admin, maxRedirects: 0 });
      expect(await headingOf(response), path).not.toBe("Sign in");
      expect([308, 404], path).toContain(response.status());
    }
  });

  test("security headers apply here too", async ({ request }) => {
    const h = (await request.get("/", { headers: admin })).headers();
    expect(h["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(h["strict-transport-security"]).toContain("includeSubDomains");
  });
});

test.describe("behind Cloudflare and Railway", () => {
  test("the Host header decides, whatever the forwarding headers say", async ({ request }) => {
    const forwarded = { "x-forwarded-proto": "https" };
    const site = await request.get("/", { headers: { ...main, ...forwarded } });
    expect(await headingOf(site)).toBe(HOME_HEADING);

    const back = await request.get("/", {
      headers: { ...admin, ...forwarded, "x-forwarded-host": ADMIN_HOST },
      maxRedirects: 0,
    });
    // Still the admin host, so the admin frame's session gate applies (the same redirect as above).
    expect(back.status()).toBe(307);
    expect(back.headers()["location"]).toBe("/session?next=%2F");
  });

  test("a spoofed X-Forwarded-Host cannot turn the main host into the admin host", async ({
    request,
  }) => {
    const response = await request.get("/", {
      headers: { ...main, "x-forwarded-host": ADMIN_HOST },
    });
    expect(await headingOf(response)).toBe(HOME_HEADING);
    const direct = await request.get("/platform", {
      headers: { ...main, "x-forwarded-host": ADMIN_HOST },
    });
    expect(direct.status()).toBe(404);
  });

  test("an unknown host is treated as the public site", async ({ request }) => {
    const response = await request.get("/", { headers: { host: "random-name.up.railway.app" } });
    expect(await headingOf(response)).toBe(HOME_HEADING);
  });
});
