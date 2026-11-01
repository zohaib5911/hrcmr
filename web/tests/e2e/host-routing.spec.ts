import { expect, test } from "@playwright/test";

import { ADMIN_HOST, BASE_URL, MAIN_HOST, headingOf } from "./helpers";

const main = { host: MAIN_HOST };
const admin = { host: ADMIN_HOST };

test.describe("main host", () => {
  test("serves the public site and the app", async ({ request }) => {
    expect(await headingOf(await request.get("/", { headers: main }))).toBe("Brand");
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
  test("serves the back office at the root", async ({ request }) => {
    const response = await request.get("/", { headers: admin });
    expect(response.status()).toBe(200);
    expect(await headingOf(response)).toBe("Platform admin");
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
    expect(await headingOf(site)).toBe("Brand");

    const back = await request.get("/", {
      headers: { ...admin, ...forwarded, "x-forwarded-host": ADMIN_HOST },
    });
    expect(await headingOf(back)).toBe("Platform admin");
  });

  test("a spoofed X-Forwarded-Host cannot turn the main host into the admin host", async ({
    request,
  }) => {
    const response = await request.get("/", {
      headers: { ...main, "x-forwarded-host": ADMIN_HOST },
    });
    expect(await headingOf(response)).toBe("Brand");
    const direct = await request.get("/platform", {
      headers: { ...main, "x-forwarded-host": ADMIN_HOST },
    });
    expect(direct.status()).toBe(404);
  });

  test("an unknown host is treated as the public site", async ({ request }) => {
    const response = await request.get("/", { headers: { host: "random-name.up.railway.app" } });
    expect(await headingOf(response)).toBe("Brand");
  });
});
