import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { registerFixture } from "../fixtures/register";

for (const theme of ["light", "dark"] as const) {
  test(`register exploration works in ${theme} theme`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    await page.emulateMedia({ colorScheme: theme });
    await page.route("**/public/register/explore*", async (route) => {
      const query = new URL(route.request().url()).searchParams;
      await route.fulfill({
        json: {
          ...registerFixture,
          page: Number(query.get("page") ?? 1),
          ...(query.get("q") === "absent" ? { total: 0, results: [] } : {}),
        },
      });
    });
    await page.goto("/sponsors");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Explore the UK sponsor register",
    );
    await expect(
      page.getByRole("status").filter({ hasText: "51 matching sponsors" }),
    ).toBeVisible();
    await expect(page.getByRole("img", { name: /Schematic map/ })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.getByRole("button", { name: "Trend", exact: true }).click();
    await expect(page.getByRole("img", { name: "Sponsor count by publication" })).toBeVisible();
    await page.getByRole("button", { name: "Table", exact: true }).click();
    await expect(page.getByRole("table", { name: "Matching sponsors" })).toContainText(
      "Stable Ltd",
    );
    const table = page.getByRole("region", { name: "Sponsor table", exact: true });
    await table.focus();
    await expect(table).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect.poll(() => table.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    await page.getByRole("button", { name: "Next page" }).click();
    await expect(page.getByText("Page 2 of 2")).toBeVisible();
    await page.getByRole("button", { name: "List", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Stable Ltd" })).toBeVisible();
    await page.getByRole("combobox", { name: "Compare window" }).selectOption("start");
    await page.getByRole("slider", { name: "Publication timeline" }).focus();
    await page.keyboard.press("ArrowLeft");
    await page.getByRole("searchbox").fill("absent");
    await page.getByRole("button", { name: "Search register" }).click();
    await expect(page.getByText(/No sponsors match these filters/)).toBeVisible();
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "51 matching sponsors" }),
    ).toBeVisible();
  });
}
