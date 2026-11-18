/** Free signup through paid entitlement, first employee, RTW and a due follow-up reminder.
 * Stripe's external checkout is represented by the existing test-server paid-plan fixture.
 */
import { request } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../../support/accounts";
import { expect, test } from "../../support/fixtures";

const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n",
);

test("a new free company subscribes, adds its first employee and reviews their RTW reminder", async ({
  browser,
}) => {
  test.setTimeout(90_000);
  const api = await request.newContext();
  const account = await createSignedInAdmin(api, newAccount("onboarding"), { plan: "free" });
  const context = await browser.newContext({ storageState: await api.storageState() });
  try {
    const page = await context.newPage();
    const headers = await csrfHeaders(context.request);
    await page.goto("/company/billing");
    await expect(page.getByText("Free", { exact: true }).first()).toBeVisible();
    const refused = await context.request.post(`${API}/employees`, {
      headers,
      data: {
        first_name: "Ravi",
        last_name: "Onboarding",
        employee_number: "FIRST-1",
        email: "ravi-onboarding@example.com",
        hire_date: "2025-01-06",
      },
    });
    expect(refused.status(), await refused.text()).toBe(402);
    expect((await refused.json()).error.code).toBe("PLAN_REQUIRED");

    // Same account and session: activation must unlock writes without a fresh sign-in.
    const paid = await context.request.post(`${API}/e2e/paid-plan`, {
      headers,
      data: { email: account.email },
    });
    expect(paid.status(), await paid.text()).toBe(200);
    await page.reload();
    await expect(page.getByText("1 year plan", { exact: true }).first()).toBeVisible();
    await page.goto("/employees/new");
    await page.getByLabel("First name", { exact: true }).fill("Ravi");
    await page.getByLabel("Last name", { exact: true }).fill("Onboarding");
    await page.getByLabel("Work email", { exact: true }).fill("ravi-onboarding@example.com");
    await page.getByLabel("Employee number", { exact: true }).fill("FIRST-1");
    await page.getByLabel("Hire date", { exact: true }).fill("6 Jan 2025");
    await page.getByRole("button", { name: "Add employee", exact: true }).click();
    await page.getByRole("grid", { name: "Employees" }).getByText("Ravi Onboarding").click();
    await expect(page.getByRole("heading", { name: "Ravi Onboarding", exact: true })).toBeVisible();
    const employee = page.url().split("/").at(-1)!;
    const users = await context.request.get(`${API}/users`);
    expect(users.status(), await users.text()).toBe(200);
    const membership = (await users.json()).users.find((user: { is_you: boolean }) => user.is_you);
    const linked = await context.request.put(`${API}/users/${membership.id}/employee`, {
      headers,
      data: { employee_id: employee },
    });
    expect(linked.status(), await linked.text()).toBe(200);
    const upload = await context.request.post(`${API}/employees/${employee}/documents`, {
      headers,
      multipart: {
        category: "rtw_evidence",
        file: { name: "rtw.pdf", mimeType: "application/pdf", buffer: PDF },
      },
    });
    expect(upload.status(), await upload.text()).toBe(201);
    expect((await upload.json()).scan_status).toBe("clean");
    await page.getByRole("button", { name: "Resolve Right to Work", exact: true }).click();
    await page.getByRole("button", { name: "Record a check", exact: true }).click();
    const sheet = page.getByRole("dialog");
    await sheet.getByLabel("Share code", { exact: true }).fill("W12345678");
    await sheet.getByRole("switch", { name: "Does permission run out?" }).click();
    const expiry = new Date(Date.now() + 21 * 86_400_000).toISOString().slice(0, 10);
    await sheet.getByLabel("Permission expires on", { exact: true }).fill(expiry);
    await sheet.getByLabel("Outcome", { exact: true }).selectOption("verified");
    await sheet
      .getByLabel("Evidence document", { exact: true })
      .selectOption((await upload.json()).file_id);
    await sheet.getByRole("button", { name: "Save", exact: true }).click();
    await expect(sheet).toBeHidden();
    const recorded = await context.request.get(`${API}/employees/${employee}/rtw-checks`);
    expect(recorded.status(), await recorded.text()).toBe(200);
    expect((await recorded.json()).status).toBe("expiring");
    await page.goto("/sponsor-compliance/reminders");
    await page
      .getByRole("article", { name: /Ravi Onboarding/ })
      .getByRole("button", { name: "Review & send", exact: true })
      .click();
    const review = page.getByRole("dialog", { name: "Review reminder", exact: true });
    await expect(review.getByText(/Ravi Onboarding/)).toBeVisible();
    await expect(review.getByRole("button", { name: "Send reminder", exact: true })).toBeEnabled();
    const sent = page.waitForResponse(
      (response) => response.url().endsWith("/send") && response.request().method() === "POST",
    );
    await review.getByRole("button", { name: "Send reminder", exact: true }).click();
    expect((await sent).status()).toBe(200);
    await expect(review).toBeHidden();
    await page.getByRole("tab", { name: "History (1)", exact: true }).click();
    await expect(
      page
        .getByRole("grid", { name: "Sent reminder history", exact: true })
        .getByText("Ravi Onboarding", { exact: true }),
    ).toBeVisible();
  } finally {
    await context.close();
    await api.dispose();
  }
});
