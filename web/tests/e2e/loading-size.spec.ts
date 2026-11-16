import { expect, test } from "../support/fixtures";

for (const path of ["/", "/dashboard"]) {
  test(`initial JavaScript bytes ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const bytes = await page.evaluate(() =>
      performance
        .getEntriesByType("resource")
        .filter((entry) => entry.name.includes("/_next/") && entry.name.includes(".js"))
        .reduce((total, entry) => total + (entry as PerformanceResourceTiming).decodedBodySize, 0),
    );
    expect(bytes).toBeGreaterThan(0);
    console.log(`INITIAL_JS ${path} ${bytes}`);
  });
}
