import type { Page } from "@playwright/test";

/**
 * Waits for every finite CSS animation and transition on the page to finish. Axe measures the
 * colours the browser is showing at that instant, so a sheet or dialog that is still fading in reads
 * as low contrast on a slow machine (CI) though it is fine once it has settled. Endless animations
 * (a skeleton's shimmer) are left alone: they never finish.
 */
export async function settled(page: Page): Promise<void> {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );
}
