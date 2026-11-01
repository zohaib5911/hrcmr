import { expect, type Locator, type Page } from "@playwright/test";

/** Opens /design (development server) and waits for it to hydrate. Returns the console problems seen. */
export async function openDesign(page: Page) {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  await page.goto("/design");
  await expect(page.getByRole("heading", { level: 1, name: "Design tokens" })).toBeVisible();
  // React has taken over the page (HydrationFlag), and the live token values have been read.
  await page.locator("html[data-hydrated]").waitFor({ state: "attached" });
  await expect(page.locator('[data-token-value="--bg"]').first()).not.toHaveText("…");
  return problems;
}

/** True when keyboard focus is somewhere inside `container`. */
export function focusInside(container: Locator) {
  return container.evaluate((element) => element.contains(document.activeElement));
}

/** The accessible name of the element that has focus ("Monday 2 November 2026", "Edit"...). */
export function focusedName(page: Page) {
  return page.evaluate(() => {
    const element = document.activeElement;
    return element?.getAttribute("aria-label") ?? element?.textContent?.trim() ?? "";
  });
}

/**
 * Presses an arrow key the way a person does: held for a moment.
 *
 * A radio group chooses the radio it moves to, but Radix moves focus on a timer after the key goes
 * down and only chooses it if the key is still held when the timer fires. Playwright's instant
 * key-down-and-up releases it first, so a plain `press` moves focus without choosing.
 */
export function pressArrow(page: Page, key: "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown") {
  return page.keyboard.press(key, { delay: 60 });
}
