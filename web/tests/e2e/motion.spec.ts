/**
 * U6.1.9: opening the command palette stays smooth on a slow phone. Chrome's CPU is slowed 4x, a
 * Playwright trace is kept with the results, and the Long Animation Frames API (frames over 50 ms)
 * is read from the key press until the palette has settled.
 *
 * Budget (decision U6.1.9 in .agent/decisions.md): no long frame while the palette animates in, and
 * at most one long frame for the opening itself, under 150 ms at 4x (about 20 ms at full speed).
 * That one frame is the modal's scroll lock re-laying-out the page, which the dialog needs for its
 * focus trap and for hiding the page from screen readers.
 */
import { expect, test } from "../support/fixtures";
import { settled } from "../support/settle";

test.use({ viewport: { width: 1280, height: 900 } });

interface Frame {
  ms: number;
  scriptMs: number;
}

test("opening the command palette on a 4x slower CPU stays within the frame budget", async ({
  page,
  context,
}, testInfo) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await settled(page);
  // Let the page finish its own start-up work, including loading the palette while idle.
  for (let i = 0; i < 2; i += 1) {
    await page.evaluate(() => new Promise((done) => requestIdleCallback(() => done(null))));
  }
  await page.waitForLoadState("networkidle");

  const cdp = await context.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  // The trace itself must not cost frames: no screenshots or DOM snapshots in it.
  await context.tracing.start({ screenshots: false, snapshots: false });

  await page.evaluate(() => {
    const store = window as unknown as { __longFrames: Frame[] };
    store.__longFrames = [];
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration <= 50) continue;
        const scripts = (entry as unknown as { scripts: { duration: number }[] }).scripts ?? [];
        store.__longFrames.push({
          ms: Math.round(entry.duration),
          scriptMs: Math.round(scripts.reduce((sum, script) => sum + script.duration, 0)),
        });
      }
    }).observe({ type: "long-animation-frame" });
  });

  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Search" })).toBeVisible();
  await settled(page);
  await page.waitForTimeout(300);

  const frames = await page.evaluate(
    () => (window as unknown as { __longFrames: Frame[] }).__longFrames,
  );
  await context.tracing.stop({ path: testInfo.outputPath("palette-trace.zip") });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  testInfo.annotations.push({ type: "long frames (ms)", description: JSON.stringify(frames) });

  expect(frames.length, JSON.stringify(frames)).toBeLessThanOrEqual(1);
  for (const frame of frames) expect(frame.ms, JSON.stringify(frames)).toBeLessThan(150);
});
