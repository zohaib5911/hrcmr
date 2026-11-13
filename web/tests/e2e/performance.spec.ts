/**
 * T22.2 web budgets on the production build: Largest Contentful Paint under 2.0 s and Cumulative
 * Layout Shift under 0.05 on the home page and the main signed-in screens. Each page is loaded once
 * to warm the server, then measured on a second, fresh load at desktop width.
 */
import type { Page } from "@playwright/test";

import { expect, test } from "../support/fixtures";

const LCP_MS = 2000;
const CLS = 0.05;
const PAGES = ["/", "/dashboard", "/employees", "/leave"] as const;

async function vitals(page: Page): Promise<{ lcp: number; cls: number }> {
  return page.evaluate(
    () =>
      new Promise<{ lcp: number; cls: number }>((resolve) => {
        let lcp = 0;
        let cls = 0;
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) lcp = Math.max(lcp, entry.startTime);
        }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries() as (PerformanceEntry & {
            value: number;
            hadRecentInput: boolean;
          })[]) {
            if (!entry.hadRecentInput) cls += entry.value;
          }
        }).observe({ type: "layout-shift", buffered: true });
        // Let the buffered entries arrive, and any late shift happen, before reading.
        setTimeout(() => resolve({ lcp, cls }), 1000);
      }),
  );
}

for (const path of PAGES) {
  test(`${path} paints its main content in under 2 s and does not shift`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    const { lcp, cls } = await vitals(page);
    expect(lcp, `${path} LCP ${Math.round(lcp)} ms`).toBeGreaterThan(0);
    expect(lcp, `${path} LCP ${Math.round(lcp)} ms`).toBeLessThan(LCP_MS);
    expect(cls, `${path} CLS ${cls.toFixed(3)}`).toBeLessThan(CLS);
  });
}
