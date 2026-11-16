/** T14.1 dashboard: the cards render for an administrator, the set-up checklist can be dismissed, and the page holds at 390 px. */
import { audit } from "../../support/axe";
import { expect, test } from "../../support/fixtures";

test("the dashboard shows the cards and the set-up checklist, which can be dismissed", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Dashboard", level: 1, exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/^(Good morning|Good afternoon|Good evening),/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Get set up", exact: true })).toBeVisible();
  await expect(page.getByText("Right to Work coverage (%)", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Employee distribution", exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 1280, height: 900 });
  const actions = page.locator('[aria-label="Quick actions"]');
  const tops = await actions
    .getByRole("link")
    .evaluateAll((links) => links.map((link) => Math.round(link.getBoundingClientRect().top)));
  expect(new Set(tops).size).toBe(1);
  await page.screenshot({ path: "/tmp/u616-dashboard-1280.png" });
  await page
    .getByRole("region", { name: "Get set up", exact: true })
    .getByRole("button", { name: "Dismiss", exact: true })
    .click();
  await expect(page.getByRole("region", { name: "Get set up", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Dashboard", level: 1, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Get set up", exact: true })).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 900 });
  await actions.getByRole("button", { name: "More", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "Upload document" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.screenshot({ path: "/tmp/u616-dashboard-390.png" });
  await audit(page, "Dashboard mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
