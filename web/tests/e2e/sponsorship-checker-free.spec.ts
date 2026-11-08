/** T15.8 free checker: a visitor who has not signed in finds a code and sees the salary table. */
import { expect, test } from "@playwright/test";

test("a visitor finds a code and sees the salary table without signing in", async ({ page }) => {
  await page.goto("/resources/tools/sponsorship-job-checker");
  await expect(
    page.getByRole("heading", { level: 1, name: "Sponsorship job checker" }),
  ).toBeVisible();

  await page.getByRole("textbox", { name: "Job title" }).fill("Adviser, sales");
  await page.getByRole("button", { name: /^7111 Sales and retail assistants$/ }).click();
  await page.getByLabel("Offered salary", { exact: true }).fill("30000");
  await page.getByRole("button", { name: "Show the salary table" }).click();

  await expect(page.getByRole("region", { name: "Salary table" })).toBeVisible();
  await expect(
    page.getByText("General guidance, not legal or immigration advice.").first(),
  ).toBeVisible();
});
