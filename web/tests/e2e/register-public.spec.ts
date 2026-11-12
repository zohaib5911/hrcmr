import { expect, test } from "@playwright/test";
import { API } from "../support/accounts";

test.use({ storageState: { cookies: [], origins: [] } });

test("register detail pages render saved publications with a fresh CSP nonce", async ({ page }) => {
  const listing = await page.request.get(`${API}/public/register/sitemap/0`);
  expect(listing.status()).toBe(200);
  const { items } = (await listing.json()) as {
    items: { stable_id: string; slug: string }[];
  };
  const sponsor = items.find((s) => s.slug === "stable-ltd");
  expect(sponsor).toBeTruthy();
  const nonces = new Set<string>();
  for (const [route, heading] of [
    ["/sponsors/regions/london", "Licensed sponsors in London"],
    ["/sponsors/changes/2026-11-11", "Register changes, 11 Nov 2026"],
    [`/sponsors/profile/${sponsor!.stable_id}/${sponsor!.slug}`, "Stable Ltd"],
    ["/sponsors/regions/london", "Licensed sponsors in London"],
  ] as const) {
    const response = await page.goto(route);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: heading, exact: true })).toBeVisible();
    const csp = response!.headers()["content-security-policy"] ?? "";
    const nonce = csp.match(/'nonce-([^']+)'/)?.[1];
    expect(nonce).toBeTruthy();
    expect(nonces.has(nonce!)).toBe(false);
    nonces.add(nonce!);
    const scriptNonces = await page
      .locator("script[nonce]")
      .evaluateAll((scripts) => scripts.map((script) => (script as HTMLScriptElement).nonce));
    expect(scriptNonces.length).toBeGreaterThan(0);
    expect(scriptNonces.every((value) => value === nonce)).toBe(true);
  }
});
