/** T7.5: real source-derived hub, action destinations, matched CSV and official dossier. */
import { readFile } from "node:fs/promises";
import { request as playwrightRequest } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const dateIn = (days: number) =>
  new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

test("Compliance hub actions reach their records, filters match exports and dossier downloads", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("hub"));
  const headers = await csrfHeaders(api);
  const ids: string[] = [];
  for (const [first_name, last_name, employee_number] of [
    ["Jaya", "Singh", "HUB100"],
    ["Luis", "Diaz", "HUB101"],
  ] as const) {
    const made = await api.post(API + "/employees", {
      headers,
      data: {
        first_name,
        last_name,
        employee_number,
        email: first_name.toLowerCase() + "@example.com",
        hire_date: "2025-01-06",
      },
    });
    expect(made.status(), await made.text()).toBe(201);
    ids.push(((await made.json()) as { id: string }).id);
  }
  const users = (await (await api.get(API + "/users")).json()) as {
    users: { user_id: string; is_you: boolean }[];
  };
  const check = await api.post(API + "/employees/" + ids[0] + "/rtw-checks", {
    headers,
    data: {
      check_type: "manual_list_b",
      list_b_group: "group1",
      permission_expires: true,
      permission_expires_on: dateIn(-1),
      check_date: dateIn(-20),
      checked_by_user_id: users.users.find((u) => u.is_you)!.user_id,
      outcome: "verified",
    },
  });
  expect(check.status(), await check.text()).toBe(201);
  for (const [doc_type, days] of [
    ["passport", 21],
    ["visa", 45],
    ["other", 75],
  ] as const) {
    const doc = await api.post(API + "/employees/" + ids[1] + "/sponsor-documents", {
      headers,
      data: {
        doc_type,
        expiry_date: dateIn(days),
        ...(doc_type === "visa" ? { visa_route: "skilled_worker" } : {}),
      },
    });
    expect(doc.status(), await doc.text()).toBe(201);
  }
  const org = await api.post(API + "/compliance/org-changes", {
    headers,
    data: {
      change_type: "address",
      change_date: "2026-08-28",
      remarks: "Company moved its main address",
    },
  });
  expect(org.status(), await org.text()).toBe(201);
  const context = await browser.newContext({ storageState: await api.storageState() });
  const page = await context.newPage();
  await page.goto("/sponsor-compliance");
  await expect(
    page.getByRole("heading", { level: 1, name: "Sponsor compliance", exact: true }),
  ).toBeVisible();
  const queue = page.getByRole("region", { name: "Needs attention", exact: true });
  await expect(queue.getByText("Change past reporting deadline", { exact: true })).toBeVisible();
  await expect(queue.getByText("Right to Work expired", { exact: true })).toBeVisible();
  await expect(page.getByText("0 of 2 hold a valid check", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Every reportable change reported on time", exact: true }),
  ).toBeVisible();
  await queue
    .getByRole("link", { name: "Record a follow-up check · Jaya Singh", exact: true })
    .click();
  await expect(page.getByRole("tab", { name: "Right to Work", exact: true })).toHaveAttribute(
    "data-state",
    "active",
  );
  await expect(
    page.getByRole("region", { name: "Current Right to Work check", exact: true }),
  ).toBeVisible();
  await page.goto("/sponsor-compliance");
  await page.getByRole("link", { name: "Not recorded: 1", exact: true }).click();
  await expect(page).toHaveURL(/rtw=NotRecorded/);
  await expect(
    page
      .getByRole("grid", { name: "Employees", exact: true })
      .getByText("Luis Diaz", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("grid", { name: "Employees", exact: true })
      .getByText("Jaya Singh", { exact: true }),
  ).toHaveCount(0);
  await page.goto("/sponsor-compliance");
  await queue
    .getByRole("link", {
      name: "Open the change log and record the report · Organisation change",
      exact: true,
    })
    .click();
  await expect(page.getByRole("tab", { name: "Organisation", exact: true })).toHaveAttribute(
    "data-state",
    "active",
  );
  await expect(
    page
      .getByRole("grid", { name: "Organisation changes", exact: true })
      .getByText("Address changed", { exact: true }),
  ).toBeVisible();
  await page.goto("/sponsor-compliance");
  const expiry = page.getByRole("region", { name: "Expiring in the next 90 days", exact: true });
  for (const heading of ["Overdue (1)", "Next 30 days (1)", "31–60 days (1)", "61–90 days (1)"])
    await expect(expiry.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  await expiry.getByLabel("Document type", { exact: true }).selectOption("passport");
  await expect(
    expiry.getByRole("link", { name: "Luis Diaz · Passport", exact: true }),
  ).toBeVisible();
  await expect(expiry.getByRole("link", { name: "Luis Diaz · Visa", exact: true })).toHaveCount(0);
  await expiry.getByRole("link", { name: "Luis Diaz · Passport", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Sponsor compliance", exact: true })).toHaveAttribute(
    "data-state",
    "active",
  );
  await page.goto("/sponsor-compliance");
  const activity = page.getByRole("region", { name: "Compliance activity", exact: true });
  await activity.getByLabel("Activity category", { exact: true }).selectOption("changes");
  await expect(activity.getByText("company · change logged", { exact: true })).toBeVisible();
  await expect(activity.getByText("employee · rtw recorded", { exact: true })).toHaveCount(0);
  const csvWait = page.waitForEvent("download");
  await activity.getByRole("button", { name: "Export CSV", exact: true }).click();
  const csv = await csvWait;
  expect(csv.suggestedFilename()).toBe("compliance-activity.csv");
  const contents = await readFile((await csv.path())!, "utf8");
  expect(contents).toContain("company.change_logged");
  expect(contents).not.toContain("employee.rtw_recorded");
  await audit(page, "Compliance hub");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await audit(page, "Compliance hub mobile");
  await page.getByRole("link", { name: "Sponsor Management Dossier", exact: true }).click();
  for (const heading of ["Holding a licence", "Right to Work", "SMS manuals"])
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: /^Employer guidance for Right to Work checks/ }),
  ).toHaveAttribute(
    "href",
    "https://www.gov.uk/government/publications/right-to-work-checks-employers-guide",
  );
  const pdfWait = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download RTW checklist", exact: true }).click();
  const pdf = await pdfWait;
  expect(pdf.suggestedFilename()).toBe("right-to-work-checklist.pdf");
  expect((await readFile((await pdf.path())!)).subarray(0, 5).toString()).toBe("%PDF-");
  await audit(page, "Dossier mobile");
  await api.dispose();
  await context.close();
});
