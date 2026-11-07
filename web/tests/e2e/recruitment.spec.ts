/** T11.1 requisitions: create, approve through the sheet, and cancel after a confirmation. */
import { expect, test } from "../support/fixtures";

test("create a requisition, approve it, and cancel another after confirming", async ({ page }) => {
  await page.goto("/recruitment");
  await expect(page.getByRole("heading", { name: "Recruitment", exact: true })).toBeVisible();
  await expect(page.getByText("Open requisitions", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "New requisition", exact: true }).first().click();
  const create = page.getByRole("dialog", { name: "New requisition", exact: true });
  await create.getByLabel("Job title", { exact: true }).fill("Warehouse operative");
  await create.getByLabel("Headcount", { exact: true }).fill("2");
  await create.getByRole("button", { name: "Create requisition", exact: true }).click();
  await expect(create).toBeHidden();
  const approved = page.getByRole("row", { name: /Warehouse operative/ });
  await expect(approved.getByText("Draft", { exact: true })).toBeVisible();

  await approved.dblclick();
  const edit = page.getByRole("dialog", { name: "Requisition", exact: true });
  await edit.getByLabel("Status", { exact: true }).selectOption("open");
  await edit.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(edit).toBeHidden();
  await expect(approved.getByText("Open", { exact: true })).toBeVisible();
  await expect(approved.getByText(/Approved /)).toBeVisible();

  await page.getByRole("button", { name: "New requisition", exact: true }).first().click();
  const second = page.getByRole("dialog", { name: "New requisition", exact: true });
  await second.getByLabel("Job title", { exact: true }).fill("Night auditor");
  await second.getByRole("button", { name: "Create requisition", exact: true }).click();
  await expect(second).toBeHidden();
  const cancelled = page.getByRole("row", { name: /Night auditor/ });
  await cancelled.dblclick();
  const detail = page.getByRole("dialog", { name: "Requisition", exact: true });
  await detail.getByRole("button", { name: "Cancel requisition", exact: true }).click();
  const confirm = page.getByRole("alertdialog", { name: "Cancel this requisition?", exact: true });
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Cancel requisition", exact: true }).click();
  await expect(detail).toBeHidden();
  await expect(cancelled.getByText("Cancelled", { exact: true })).toBeVisible();
});

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
