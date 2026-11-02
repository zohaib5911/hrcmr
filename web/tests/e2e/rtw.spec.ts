/** T7.1: real RTW records/corrections; file scanning is covered by the API service tests. */
import { request as playwrightRequest } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("Right to Work conditionals, explicit saves, evidence selection, correction and directory links", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("rtw"));
  const made = await api.post(API + "/employees", {
    headers: await csrfHeaders(api),
    data: {
      first_name: "Rita",
      last_name: "Shah",
      email: "rita@example.com",
      employee_number: "RTW100",
      hire_date: "2025-01-06",
    },
  });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const context = await browser.newContext({ storageState: await api.storageState() });
  await api.dispose();
  const page = await context.newPage();
  let saves = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/rtw-checks")) saves++;
  });
  // The e2e API has no object-store configuration. The real scanning, evidence binding and
  // signed downloads are checked in tests/db/test_rtw.py; here verify the upload/picker contract.
  let uploads = 0;
  const evidence = {
    id: "11111111-1111-4111-8111-111111111111",
    file_id: "22222222-2222-4222-8222-222222222222",
    file_name: "rtw-proof.pdf",
    category: "rtw_evidence",
    notes: null,
    size: 100,
    scan_status: "clean",
    uploaded_at: new Date().toISOString(),
  };
  await page.route("**/employees/" + id + "/documents", async (route) => {
    if (route.request().method() === "POST") {
      uploads++;
      expect(route.request().postData()).toContain("rtw_evidence");
      return route.fulfill({ status: 201, json: evidence });
    }
    return route.fulfill({ json: uploads ? [evidence] : [] });
  });
  await page.goto("/employees/" + id);
  await expect(page.getByRole("heading", { level: 1, name: "Rita Shah" })).toBeVisible();
  await page.getByRole("button", { name: "Resolve Right to Work", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Right to Work", exact: true })).toHaveAttribute(
    "data-state",
    "active",
  );
  await page.getByRole("button", { name: "Record a check", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("link", { name: "Check on GOV.UK" })).toHaveAttribute(
    "href",
    "https://www.gov.uk/view-right-to-work",
  );
  await expect(dialog.getByLabel("Share code", { exact: true })).toBeVisible();
  await dialog.getByRole("switch", { name: "Does permission run out?" }).click();
  await expect(dialog.getByLabel("Permission expires on", { exact: true })).toBeVisible();
  await dialog.getByLabel("Check type", { exact: true }).selectOption("idsp_digital");
  await expect(dialog.getByLabel("Share code", { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel("Permission expires on", { exact: true })).toHaveCount(0);
  await dialog.getByLabel("Certified IDSP provider", { exact: true }).fill("Certified provider");
  await dialog
    .getByLabel("Eligible identity document", { exact: true })
    .selectOption("irish_passport_card");
  await dialog.getByLabel("Check type", { exact: true }).selectOption("manual_list_b");
  await expect(dialog.getByLabel("Certified IDSP provider", { exact: true })).toHaveCount(0);
  await dialog.getByLabel("List B group", { exact: true }).selectOption("group2");
  await expect(dialog.getByLabel("Permission expires on", { exact: true })).toBeVisible();
  await dialog.getByLabel("Check type", { exact: true }).selectOption("manual_list_a");
  await expect(dialog.getByLabel("List B group", { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel("Permission expires on", { exact: true })).toHaveCount(0);
  await dialog.getByLabel("Check type", { exact: true }).selectOption("online_share_code");
  await dialog.getByRole("switch", { name: "Does permission run out?" }).click();
  await dialog.getByLabel("Share code", { exact: true }).fill("W12345678");
  await dialog.getByLabel("Outcome", { exact: true }).selectOption("verified");
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "rtw-proof.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF\n"),
  });
  await dialog.getByRole("heading").click();
  expect(uploads).toBe(0);
  expect(saves).toBe(0);
  await dialog.getByRole("button", { name: "Upload evidence", exact: true }).click();
  await expect(dialog.getByLabel("Evidence document", { exact: true })).toHaveValue(
    evidence.file_id,
  );
  expect(uploads).toBe(1);
  expect(saves).toBe(0);
  // Save without the browser fixture's mocked file; the server must derive Evidence missing.
  await dialog.getByLabel("Evidence document", { exact: true }).selectOption("");
  await dialog.getByRole("button", { name: "Save", exact: true }).focus();
  await dialog.getByRole("heading").click();
  expect(saves).toBe(0);
  await audit(page, "Right to Work check sheet", { modal: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(1);
  const current = page.getByRole("region", { name: "Current Right to Work check", exact: true });
  await expect(current.getByLabel("Right to Work: Evidence missing")).toBeVisible();
  await expect(current.getByText("W12345678", { exact: true })).toHaveCount(0);
  await expect(current.getByText(/678$/)).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await current.getByRole("button", { name: "Evidence sheet PDF", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/^rtw-.*\.pdf$/);
  await page.goto("/employees?rtw=EvidenceMissing");
  await expect(page.getByLabel("Right to Work", { exact: true })).toHaveValue("EvidenceMissing");
  await expect(page.getByRole("grid").getByText("Rita Shah")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.goto("/employees?rtw=Verified");
  await expect(page.getByText("Nobody matches", { exact: true })).toBeVisible();
  await page.goto("/employees?rtw=NeedsAttention");
  await expect(page.getByRole("grid").getByText("Rita Shah")).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/employees/" + id);
  await page.getByRole("tab", { name: "Right to Work", exact: true }).click();
  await current.getByRole("button", { name: "Correct check", exact: true }).click();
  await expect(dialog.getByLabel("Share code", { exact: true })).toHaveValue("");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    dialog.getByText("Enter a reason for the correction.", { exact: true }),
  ).toBeVisible();
  expect(saves).toBe(1);
  await dialog.getByLabel("Check type", { exact: true }).selectOption("manual_list_a");
  await dialog.getByLabel("Outcome", { exact: true }).selectOption("pending");
  await dialog
    .getByLabel("Reason for correction", { exact: true })
    .fill("Corrected the recorded check type");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(2);
  await expect(current.getByLabel("Right to Work: Pending")).toBeVisible();
  const history = page.getByRole("region", { name: "Right to Work history", exact: true });
  await expect(history.getByText("Home Office online check", { exact: true })).toBeVisible();
  await expect(history.getByText("Superseded", { exact: true })).toBeVisible();
  await expect(history.getByRole("button", { name: "Correct check", exact: true })).toHaveCount(0);
  await audit(page, "Right to Work history");
  await context.close();
});
