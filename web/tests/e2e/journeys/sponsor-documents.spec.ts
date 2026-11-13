/** T7.2: explicit document/version/renewal/withdrawal saves and the sponsored register. */
import { request as playwrightRequest } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../../support/accounts";
import { audit } from "../../support/axe";
import { expect, test } from "../../support/fixtures";

const dateAfter = (days: number) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.now() + days * 86_400_000));

test("Sponsor documents save explicitly, retain versions, plan renewals and withdraw with reasons", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("sponsor"));
  const made = await api.post(API + "/employees", {
    headers: await csrfHeaders(api),
    data: {
      first_name: "Sophie",
      last_name: "Khan",
      email: "sophie@example.com",
      employee_number: "SP100",
      hire_date: "2025-01-06",
    },
  });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const context = await browser.newContext({ storageState: await api.storageState() });
  await api.dispose();
  const page = await context.newPage();
  let saves = 0;
  let uploads = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("sponsor-documents")) saves++;
  });
  const proof = {
    id: "11111111-1111-4111-8111-111111111111",
    file_id: "22222222-2222-4222-8222-222222222222",
    file_name: "visa-proof.pdf",
    category: "id_document",
    notes: null,
    size: 100,
    scan_status: "clean",
    uploaded_at: new Date().toISOString(),
  };
  // Storage/scanning and evidence isolation use real services in test_sponsor_documents.py.
  await page.route("**/employees/" + id + "/documents", async (route) => {
    if (route.request().method() === "POST") {
      uploads++;
      expect(route.request().postData()).toContain("id_document");
      return route.fulfill({ status: 201, json: proof });
    }
    return route.fulfill({ json: uploads ? [proof] : [] });
  });
  await page.goto("/employees/" + id);
  await page.getByRole("tab", { name: "Sponsor compliance", exact: true }).click();
  for (const label of [
    "Visa",
    "Passport",
    "DBS certificate",
    "EUSS status",
    "National ID",
    "Other",
  ])
    await expect(
      page.getByRole("region", { name: label + " document", exact: true }),
    ).toBeVisible();
  const visa = page.getByRole("region", { name: "Visa document", exact: true });
  await visa.getByRole("button", { name: "Add Visa", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("eVisa or visa reference", { exact: true }).fill("VISA-123456789");
  await dialog.getByLabel("Issuing country", { exact: true }).fill("gb");
  await dialog.getByLabel("Visa route", { exact: true }).selectOption("health_care_worker");
  await dialog.getByLabel("CoS number", { exact: true }).fill("COS-987654321");
  await dialog.getByLabel("SOC code", { exact: true }).fill("6135");
  // "Find code" opens the checker in a sheet over the form. Closing it leaves the form as it was.
  await dialog.getByRole("button", { name: "Find code", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Find the SOC code" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Job title" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Find the SOC code" })).toHaveCount(0);
  await expect(dialog.getByLabel("SOC code", { exact: true })).toHaveValue("6135");
  await dialog.getByLabel("Sponsored annual salary", { exact: true }).fill("32000");
  await dialog.getByLabel("Expiry date", { exact: true }).fill(dateAfter(120));
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "visa-proof.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF\n"),
  });
  await dialog.getByRole("heading").click();
  expect(saves).toBe(0);
  expect(uploads).toBe(0);
  await dialog.getByRole("button", { name: "Upload evidence", exact: true }).click();
  await expect(dialog.getByLabel("Evidence document", { exact: true })).toHaveValue(proof.file_id);
  expect(uploads).toBe(1);
  expect(saves).toBe(0);
  await dialog.getByLabel("Evidence document", { exact: true }).selectOption("");
  await audit(page, "Sponsor document sheet", { modal: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(1);
  await expect(visa.getByText("Version 1", { exact: true })).toBeVisible();
  await expect(visa.getByText("Health and Care Worker", { exact: true })).toBeVisible();
  await expect(visa.getByText("£32,000.00", { exact: true })).toBeVisible();
  await expect(visa.getByText("VISA-123456789", { exact: true })).toHaveCount(0);
  await expect(visa.getByText("COS-987654321", { exact: true })).toHaveCount(0);
  await expect(visa.getByText(/789$/)).toBeVisible();
  await visa.getByRole("button", { name: "Plan renewal", exact: true }).click();
  await dialog.getByLabel("Renewal target date", { exact: true }).fill(dateAfter(14));
  await dialog.getByLabel("Renewal notes", { exact: true }).fill("Request renewed evidence");
  await dialog.getByRole("heading").click();
  expect(saves).toBe(1);
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(2);
  await expect(visa.getByText("Request renewed evidence", { exact: true })).toBeVisible();
  await expect(visa.getByText(dateAfter(120), { exact: true })).toBeVisible();
  await page.goto("/sponsor-compliance/migrant-employees");
  await expect(page.getByRole("heading", { level: 1, name: "Sponsored employees" })).toBeVisible();
  await expect(page.getByRole("grid").getByText("Sophie Khan", { exact: true })).toBeVisible();
  await page
    .getByLabel("Visa route", { exact: true })
    .filter({ visible: true })
    .selectOption("scale_up");
  await expect(page.getByText("Nobody matches", { exact: true })).toBeVisible();
  await page
    .getByLabel("Visa route", { exact: true })
    .filter({ visible: true })
    .selectOption("all");
  await page.getByRole("searchbox").fill("6135");
  await expect(page.getByRole("grid").getByText("Sophie Khan", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("list", { name: "Sponsored employees", exact: true })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await audit(page, "Sponsored employees mobile");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/employees/" + id);
  await page.getByRole("tab", { name: "Sponsor compliance", exact: true }).click();
  await visa.getByRole("button", { name: "Update Visa", exact: true }).click();
  await expect(dialog.getByLabel("eVisa or visa reference", { exact: true })).toHaveValue("");
  await expect(dialog.getByLabel("CoS number", { exact: true })).toHaveValue("");
  await dialog.getByLabel("Visa route", { exact: true }).selectOption("euss_settled");
  await dialog.getByRole("heading").click();
  expect(saves).toBe(2);
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(3);
  await expect(visa.getByText("Version 2", { exact: true })).toBeVisible();
  await visa.getByText("Visa history (1)", { exact: true }).click();
  await expect(visa.getByText("Version 1", { exact: true })).toBeVisible();
  await expect(visa.getByText("Superseded", { exact: true })).toBeVisible();
  await page.goto("/sponsor-compliance/migrant-employees");
  await expect(
    page.getByRole("heading", { level: 2, name: "No sponsored employees yet" }),
  ).toBeVisible();
  await page.goto("/employees/" + id);
  await page.getByRole("tab", { name: "Sponsor compliance", exact: true }).click();
  await visa.getByRole("button", { name: "Withdraw", exact: true }).click();
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog.getByText("Enter a reason for withdrawal.", { exact: true })).toBeVisible();
  expect(saves).toBe(3);
  await dialog
    .getByLabel("Reason for withdrawal", { exact: true })
    .fill("Incorrect document retained for audit");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(4);
  await expect(visa.getByText("No current visa recorded.", { exact: true })).toBeVisible();
  await visa.getByText("Visa history (2)", { exact: true }).click();
  await expect(visa.getByText("Withdrawn", { exact: true })).toBeVisible();
  await expect(
    visa.getByText("Incorrect document retained for audit", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("region", { name: "Passport document", exact: true })
    .getByRole("button", { name: "Add Passport", exact: true })
    .click();
  await expect(dialog.getByLabel("Document reference", { exact: true })).toBeVisible();
  await expect(dialog.getByLabel("Visa route", { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel("Sponsored annual salary", { exact: true })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Sponsor compliance record PDF", exact: true }).click();
  const pdf = await download;
  expect(pdf.suggestedFilename()).toBe("sponsor-record-" + id + ".pdf");
  expect(await pdf.failure()).toBeNull();
  await audit(page, "Sponsor document history");
  await context.close();
});
