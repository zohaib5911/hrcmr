import { expect, test } from "@playwright/test";
import { marketingPages } from "../../lib/seo";

test.use({ storageState: { cookies: [], origins: [] } });

test("published pages have unique canonicals, social images and nonce-protected structured data", async ({
  page,
  request,
}) => {
  const canonicals = new Set<string>();
  for (const [path] of marketingPages) {
    await page.goto(path);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(new URL(canonical!).pathname).toBe(path);
    expect(canonicals.has(canonical!)).toBe(false);
    canonicals.add(canonical!);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /\S/);
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute("content", canonical!);
    const image = await page.locator('meta[property="og:image"]').getAttribute("content");
    expect(image).toContain("opengraph-image");
    const scripts = page.locator('script[type="application/ld+json"]');
    expect(await scripts.count()).toBeGreaterThanOrEqual(2);
    for (const script of await scripts.all()) {
      expect(await script.evaluate((node) => (node as HTMLScriptElement).nonce)).toBeTruthy();
      expect(JSON.parse((await script.textContent())!)["@context"]).toBe("https://schema.org");
    }
  }
  await page.goto("/");
  const imageUrl = await page.locator('meta[property="og:image"]').getAttribute("content");
  const image = await request.get(new URL(imageUrl!).pathname);
  expect(image.ok()).toBe(true);
  expect(image.headers()["content-type"]).toContain("image/png");
  const sitemap = await request.get("/sitemap.xml");
  expect(await sitemap.text()).not.toMatch(/\/legal\/|\/vs\/|\/platform\//);
  expect(await (await request.get("/robots.txt")).text()).toContain("Disallow: /");
});

test("drafts remain noindex and no optional trackers load before or after consent", async ({
  page,
}) => {
  const external: string[] = [];
  page.on("request", (request) => {
    if (!new URL(request.url()).hostname.match(/^(localhost|127\.0\.0\.1)$/))
      external.push(request.url());
  });
  await page.goto("/legal/privacy");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await page.getByRole("button", { name: "Reject all", exact: true }).click();
  await page.getByRole("button", { name: "Cookie settings", exact: true }).click();
  await page.getByRole("switch", { name: "Marketing" }).click();
  await page.getByRole("button", { name: "Save choices" }).click();
  await page.reload();
  await expect(page.locator('[data-consent-state="decided"]')).toBeAttached();
  expect(external).toEqual([]);
});
