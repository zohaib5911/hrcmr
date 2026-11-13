import { expect, test } from "../../support/fixtures";

test("add a candidate and record a right-to-work check", async ({ page }) => {
  await page.goto("/recruitment");
  await page.getByRole("tab", { name: /^Candidates/ }).click();
  await page.getByRole("button", { name: "Add candidate", exact: true }).first().click();
  const sheet = page.getByRole("dialog", { name: "Add candidate", exact: true });
  await sheet.getByLabel("First name", { exact: true }).fill("Mira");
  await sheet.getByLabel("Last name", { exact: true }).fill("Sato");
  await sheet.getByRole("button", { name: "Add candidate", exact: true }).click();
  await expect(page).toHaveURL(/\/recruitment\/candidates\//);
  await expect(page.getByRole("heading", { name: "Mira Sato", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Right to Work", exact: true }).click();
  await page.getByLabel("Outcome", { exact: true }).selectOption("verified");
  await page.getByRole("button", { name: "Record check", exact: true }).click();
  await expect(page.getByText("Evidence missing", { exact: true }).first()).toBeVisible();
});
