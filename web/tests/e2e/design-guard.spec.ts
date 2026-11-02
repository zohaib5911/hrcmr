import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

// The /design page lists every token and is for development only. A production build must not
// contain it at all (see `pageExtensions` in next.config.ts); the "design" project in design.spec.ts
// covers the page itself against a development server.
test.describe("the design page does not exist in production", () => {
  for (const route of ["/design", "/design/", "/design/anything", "/Design"]) {
    test(`${route} is an ordinary 404 that says nothing about the page`, async ({ request }) => {
      const response = await request.get(route);
      expect(response.status()).toBe(404);
      const body = await response.text();
      expect(body).not.toContain("Design tokens");
    });
  }

  test("/design is a 404 on the admin host too", async ({ request }) => {
    const response = await request.get("/design", { headers: { host: "admin.localhost:3100" } });
    expect(response.status()).toBe(404);
  });

  test("the production build has no design route and none of its code", async () => {
    const next = path.resolve(__dirname, "../../.next");
    const routes = Object.values(
      JSON.parse(readFileSync(path.join(next, "app-path-routes-manifest.json"), "utf8")) as Record<
        string,
        string
      >,
    );
    // Only the design page itself: a page such as /company/designations is a different route.
    expect(routes.filter((route) => route === "/design" || route.startsWith("/design/"))).toEqual(
      [],
    );
    expect(existsSync(path.join(next, "server/app/design"))).toBe(false);
  });
});
