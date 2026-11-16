/**
 * U6.1.9: opening the command palette stays smooth on a slow phone. Chrome's CPU is slowed 4x, a
 * Playwright trace is kept with the results, and the Long Animation Frames API must report no
 * frame over 50 ms between the key press and the palette having settled.
 */
import { expect, test } from "../support/fixtures";
import { settled } from "../support/settle";

test.use({ viewport: { width: 1280, height: 900 } });

test("opening the command palette on a 4x slower CPU has no long frames", async ({
  page,
  context,
}, testInfo) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await settled(page);
  // Let the page finish its own start-up work before measuring.
  await page.evaluate(() => new Promise((done) => requestIdleCallback(() => done(null))));

  const cdp = await context.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await context.tracing.start({ screenshots: true, snapshots: false });

  await page.evaluate(() => {
    const store = window as unknown as { __longFrames: number[] };
    store.__longFrames = [];
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 50) store.__longFrames.push(Math.round(entry.duration));
      }
    }).observe({ type: "long-animation-frame" });
  });

  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Search" })).toBeVisible();
  await settled(page);
  await page.waitForTimeout(300);

  const longFrames = await page.evaluate(
    () => (window as unknown as { __longFrames: number[] }).__longFrames,
  );
  await context.tracing.stop({ path: testInfo.outputPath("palette-trace.zip") });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  expect(longFrames).toEqual([]);
});
