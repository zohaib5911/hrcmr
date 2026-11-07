/** T10.1: scanned company library, review filters, metadata edits and retained archives. */
import { API } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n",
);

test("upload, review, filter, download, edit and archive a company document", async ({
  page,
  context,
}) => {
  const today = (await (await context.request.get(`${API}/documents`)).json()).today as string;
  const review = new Date(`${today}T12:00:00Z`);
  review.setUTCDate(review.getUTCDate() + 30);
  await page.goto("/documents");
  await expect(
    page.getByRole("heading", { level: 2, name: "No documents yet", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "person’s profile", exact: true })).toHaveAttribute(
    "href",
    "/employees",
  );
  await page.getByRole("button", { name: "Upload document", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Upload document", exact: true });
  await add.getByRole("button", { name: "Upload document", exact: true }).click();
  await expect(add.getByText("Enter a document title.", { exact: true }).first()).toBeVisible();
  await add.getByLabel("Title", { exact: true }).fill("Insurance 100% cover");
  await add.getByLabel("Category", { exact: true }).selectOption("insurance");
  await add
    .getByLabel("Next review date (optional)", { exact: true })
    .fill(review.toISOString().slice(0, 10));
  await add
    .getByLabel(/Company document file/)
    .setInputFiles({ name: "company-policy.pdf", mimeType: "application/pdf", buffer: PDF });
  await add.getByRole("button", { name: "Upload document", exact: true }).click();
  await expect(add).toBeHidden();
  const table = page.getByRole("grid", { name: "Company documents", exact: true });
  await expect(table.getByText("Insurance 100% cover", { exact: true })).toBeVisible();
  await expect(table.getByText("Review due", { exact: true })).toBeVisible();
  await expect(table.getByText("Scan clean", { exact: true })).toBeVisible();
  await page.getByLabel("Search documents", { exact: true }).fill("%");
  await expect(table.getByText("Insurance 100% cover", { exact: true })).toBeVisible();
  await page.getByLabel("Document category", { exact: true }).selectOption("hr_template");
  await expect(
    page.getByRole("heading", { name: "No matching documents", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Document category", { exact: true }).selectOption("insurance");
  await page.getByRole("checkbox", { name: "Review due within 30 days", exact: true }).check();
  await expect(table.getByText("Insurance 100% cover", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Insurance 100% cover", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("company-policy.pdf");
  await page.getByRole("checkbox", { name: "Review due within 30 days", exact: true }).uncheck();
  await page.getByRole("button", { name: "Edit Insurance 100% cover", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "Edit document", exact: true });
  await edit.getByLabel("Title", { exact: true }).fill("Insurance reviewed");
  await edit.getByLabel("Next review date (optional)", { exact: true }).fill("");
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "mobile company document edit", { modal: true });
  await edit.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(edit).toBeHidden();
  await page.getByLabel("Search documents", { exact: true }).fill("");
  const cards = page.getByRole("list", { name: "Company documents", exact: true });
  await expect(cards.getByText("Insurance reviewed", { exact: true })).toBeVisible();
  await expect(cards.getByText("No review date", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit Insurance reviewed", exact: true }).click();
  await edit.getByRole("button", { name: "Archive", exact: true }).click();
  const confirm = page.getByRole("alertdialog", { name: "Archive this document?", exact: true });
  await confirm.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(edit).toBeHidden();
  await expect(
    page.getByRole("heading", { name: "No matching documents", exact: true }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: "Show archived", exact: true }).check();
  await expect(cards.getByText("Archived", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Edit Insurance reviewed", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Download Insurance reviewed", exact: true }),
  ).toBeEnabled();
  await audit(page, "mobile company document archive");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
