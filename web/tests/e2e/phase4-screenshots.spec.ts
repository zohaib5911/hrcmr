/**
 * Design QA screenshots of the Company pages (plan 5.12 and Phase 4), in light and dark at 1280 px
 * and 390 px. They are the evidence kept in docs/screenshots/phase-4/, so this runs only on request:
 *
 *   SCREENSHOTS=1 pnpm exec playwright test phase4-screenshots --project=production
 */
import path from "node:path";

import { expect, test } from "@playwright/test";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-4");
const SIZES = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "phone", width: 390, height: 844 },
] as const;

const PAGES = [
  { slug: "company", path: "/company", heading: "Company" },
  { slug: "locations", path: "/company/locations", heading: "Locations" },
  { slug: "departments", path: "/company/departments", heading: "Departments" },
  { slug: "designations", path: "/company/designations", heading: "Designations" },
  { slug: "key-personnel", path: "/company/key-personnel", heading: "Key personnel" },
  {
    slug: "compliance-documents",
    path: "/company/compliance-documents",
    heading: "Compliance documents",
  },
  { slug: "working-pattern", path: "/company/working-pattern", heading: "Working pattern" },
  { slug: "holidays", path: "/holiday-management?year=2026", heading: "Holidays" },
  { slug: "trading-hours", path: "/company/trading-hours", heading: "Trading hours" },
  { slug: "bank-accounts", path: "/company/bank-accounts", heading: "Bank accounts" },
  { slug: "tax-codes", path: "/company/tax-codes", heading: "Tax codes" },
  { slug: "payment-types", path: "/company/payment-types", heading: "Payment types" },
  { slug: "pay-bands", path: "/company/pay-bands", heading: "Pay bands" },
  { slug: "pay-schedules", path: "/company/pay-schedules", heading: "Pay schedules" },
] as const;

test.skip(!process.env.SCREENSHOTS, "Screenshots are only taken on request (SCREENSHOTS=1).");

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const size of SIZES) {
      for (const screen of PAGES) {
        test(`${screen.slug} (${size.name})`, async ({ page }) => {
          await page.setViewportSize({ width: size.width, height: size.height });
          await page.goto(screen.path);
          await expect(page.getByRole("heading", { level: 1, name: screen.heading })).toBeVisible();
          await page.waitForLoadState("networkidle");
          await page.evaluate(() => document.fonts.ready);
          await page.mouse.move(0, 0);
          await page.waitForTimeout(400);
          await page.screenshot({
            path: path.join(OUT, `${screen.slug}-${colorScheme}-${size.name}.png`),
            fullPage: true,
          });
        });
      }
    }
  });
}
