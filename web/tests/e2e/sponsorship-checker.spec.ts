/** T15.6 sponsorship checker: a job is checked, its code confirmed, and the PDF report downloaded. */
import { expect, test } from "../support/fixtures";

const DISCLAIMER = "General guidance, not legal or immigration advice.";

test("check a job, confirm the code and download the PDF report", async ({ page }) => {
  await page.goto("/sponsorship-checker");
  await expect(page.getByRole("heading", { name: "Sponsorship checker" })).toBeVisible();
  await expect(page.getByText(DISCLAIMER).first()).toBeVisible();

  await page.waitForLoadState("networkidle");
  await expect(page.getByLabel("Offered salary", { exact: true })).toHaveCount(1);
  await page.getByRole("textbox", { name: "Job title" }).fill("Adviser, sales");
  await page.getByLabel("Offered salary", { exact: true }).fill("30000");
  await page.getByRole("button", { name: "Check this job" }).click();

  // The best match is the first "Check this code" button; choosing it saves a draft check.
  await page.getByRole("button", { name: "Check this code" }).first().click();
  await expect(
    page.getByRole("heading", { name: "7111 Sales and retail assistants" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Confirm this code" }).click();
  await expect(page.getByRole("button", { name: "Download the report (PDF)" })).toBeVisible();

  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download the report (PDF)" }).click();
  expect((await downloaded).suggestedFilename()).toBe("soc-check-7111.pdf");

  await expect(page.getByText(DISCLAIMER).first()).toBeVisible();
});
