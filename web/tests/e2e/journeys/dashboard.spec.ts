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
  await audit(page, "Dashboard mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
