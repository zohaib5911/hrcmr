/** T25.6: public reading frames, date presentation and recovery across the affected routes. */
import { expect, test } from "@playwright/test";
import { audit } from "../support/axe";
import { API } from "../support/accounts";

test.use({ storageState: { cookies: [], origins: [] } });
const ROUTES = [
  "/legal/ai-policy",
  "/legal/complaints",
  "/legal/cookies",
  "/legal/dpa",
  "/legal/privacy",
  "/legal/refunds",
  "/legal/register-terms",
  "/legal/resources-disclaimer",
  "/legal/subprocessors",
  "/legal/terms",
  "/resources",
  "/resources/guides",
  "/resources/guides/follow-up-right-to-work-checks",
  "/resources/guides/right-to-work-changes-october-2026",
  "/resources/guides/right-to-work-checks",
  "/resources/guides/sponsor-licence-audit-preparation",
  "/resources/guides/sponsor-reporting-duties",
  "/resources/guides/statutory-holiday-entitlement",
  "/resources/templates",
  "/resources/tools",
  "/resources/tools/holiday-entitlement-calculator",
  "/resources/tools/ilr-citizenship-checker",
  "/resources/tools/right-to-work-october-2026-checker",
  "/resources/tools/risk-assessment-template",
  "/resources/tools/skilled-worker-ilr-salary-calculator",
  "/resources/tools/skilled-worker-visa-checker",
  "/resources/tools/sponsor-licence-cost-calculator",
  "/resources/tools/sponsor-reporting-deadline-calculator",
  "/resources/tools/sponsorship-job-checker",
  "/resources/tools/uk-employer-cost-calculator",
  "/resources/tools/uk-minimum-wage-underpayment-checker",
  "/resources/tools/uk-notice-pay-calculator",
  "/resources/tools/uk-redundancy-pay-calculator",
  "/resources/tools/uk-sick-pay-calculator",
  "/resources/tools/uk-take-home-salary-calculator",
  "/sponsors",
  "/sponsors/changes",
  "/sponsors/methodology",
  "/sponsors/terms",
];

for (const colorScheme of ["light", "dark"] as const) {
  for (const width of [390, 1280]) {
    test(`${colorScheme} public reading pages at ${width}px`, async ({ page }) => {
      test.setTimeout(360_000);
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ colorScheme });
      const listing = await page.request.get(`${API}/public/register/sitemap/0`);
      expect(listing.ok()).toBe(true);
      const { items } = await listing.json();
      const sponsor = items.find((item: { slug: string }) => item.slug === "stable-ltd");
      expect(sponsor).toBeTruthy();
      const paths = [
        ...ROUTES,
        "/sponsors/regions/london",
        "/sponsors/changes/2026-11-11",
        `/sponsors/profile/${sponsor.stable_id}/${sponsor.slug}`,
        "/compare/hr-software",
        "/vs/example",
      ];
      for (const path of paths) {
        await test.step(path, async () => {
          const response = await page.goto(path);
          const missing = path.startsWith("/compare/") || path.startsWith("/vs/");
          expect(response?.status()).toBe(missing ? 404 : 200);
          await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
          await page.waitForLoadState("networkidle");
          const reject = page.getByRole("button", { name: "Reject all", exact: true });
          if (await reject.isVisible()) await reject.click();
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
            ),
            path,
          ).toBeLessThanOrEqual(0);
          if (path.startsWith("/resources") || path.startsWith("/legal/")) {
            const prose = page.locator("main .text-lead").first();
            await expect(prose).toBeVisible();
            expect(
              await prose.evaluate((node) => parseFloat(getComputedStyle(node).fontSize)),
            ).toBeGreaterThanOrEqual(19);
          }
          for (const time of await page.locator("main time[datetime]").all()) {
            const iso = await time.getAttribute("datetime");
            expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}$/);
            await expect(time).toHaveText(/^\d{1,2} [A-Z][a-z]{2} \d{4}$/);
          }
          if (missing)
            await expect(page.getByRole("link", { name: "Go to the home page" })).toBeVisible();
          await audit(page, `${colorScheme} ${width}px ${path}`);
        });
      }
    });
  }
  test(`${colorScheme} public date input, validation, presets and reset`, async ({ page }) => {
    await page.emulateMedia({ colorScheme });
    await page.goto("/resources/tools/sponsor-reporting-deadline-calculator");
    const date = page.getByRole("textbox", { name: "Event date", exact: true });
    await page.getByLabel("Event type", { exact: true }).selectOption("org-change");
    await date.fill("31 Feb 2026");
    await date.press("Tab");
    await expect(page.getByText("Enter a date like 1 Nov 2026", { exact: true })).toBeVisible();
    await date.fill("28 Aug 2026");
    await date.press("Tab");
    await expect(page.getByRole("region", { name: "Deadline result" })).toContainText(
      "28 Sep 2026",
    );
    await page.getByRole("button", { name: "Worker did not start, Scotland" }).click();
    await expect(date).toHaveValue("27 Nov 2026");
    await expect(page.getByRole("region", { name: "Deadline result" })).toContainText(
      "14 Dec 2026",
    );
    await page.getByRole("button", { name: "Choose event date from a calendar" }).click();
    await expect(
      page.getByRole("dialog", { name: "Choose event date", exact: true }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Choose event date", exact: true })).toBeHidden();
    await page.getByRole("button", { name: "Reset answers" }).click();
    await expect(date).toHaveValue("");
    await audit(page, `${colorScheme} public date reset`);
  });
}
