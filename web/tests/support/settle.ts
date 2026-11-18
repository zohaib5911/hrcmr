import type { Page } from "@playwright/test";

/**
 * Waits for every finite CSS animation and transition on the page to finish. Axe measures the
 * colours the browser is showing at that instant, so a sheet or dialog that is still fading in reads
 * as low contrast on a slow machine (CI) though it is fine once it has settled. Endless animations
 * (a skeleton's shimmer) are left alone: they never finish.
 *
 * Rows that arrive a moment later start their own entrance (U6.1.9 stagger-rise), so this checks
 * again after each round, until a frame passes with nothing running (at most five rounds).
 */
export async function settled(page: Page): Promise<void> {
  for (let round = 0; round < 5; round += 1) {
    const waited = await page.evaluate(async () => {
      const running = document
        .getAnimations()
        .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
        .filter((animation) => animation.playState !== "finished");
      await Promise.all(running.map((animation) => animation.finished.catch(() => undefined)));
      // One more frame, so anything rendered meanwhile has started its own animation.
      await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
      return running.length;
    });
    if (waited === 0) return;
  }
}
