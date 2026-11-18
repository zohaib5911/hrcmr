/** T7.3: official-calendar targets, retained snapshots, reporting and organisation CRUD. */
import { request as playwrightRequest } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("Worker changes keep a snapshot, count the bank holiday and record who reported", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("changes"));
  const made = await api.post(API + "/employees", {
    headers: await csrfHeaders(api),
    data: {
      first_name: "Nadia",
      last_name: "Grant",
      email: "nadia@example.com",
      employee_number: "COC100",
      hire_date: "2025-01-06",
    },
  });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const passport = await api.post(API + "/employees/" + id + "/sponsor-documents", {
    headers: await csrfHeaders(api),
    data: { doc_type: "passport", reference_number: "PASSPORT12345" },
  });
  expect(passport.status(), await passport.text()).toBe(201);
  const documentId = ((await passport.json()) as { id: string }).id;
  const context = await browser.newContext({ storageState: await api.storageState() });
  await api.dispose();
  const page = await context.newPage();
  let saves = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && /\/changes(?:\/|$)/.test(new URL(request.url()).pathname)) {
      saves++;
      const body = request.postDataJSON() as Record<string, unknown>;
      if ("change_type" in body) {
        expect(body.documents_snapshot).toEqual([documentId]);
        expect(body.ack_inform_hr).toBe(true);
      }
    }
  });
  await page.goto("/employees/" + id);
  await page.getByRole("tab", { name: "Sponsor compliance", exact: true }).click();
  const log = page.getByRole("region", { name: "Change of circumstances", exact: true });
  await log.getByRole("button", { name: "Log a change", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Log a change", exact: true });
  await dialog.getByLabel("Change type", { exact: true }).selectOption("salary_reduced");
  await dialog.getByLabel("Reportable event date", { exact: true }).fill("28 Aug 2026");
  await dialog.getByRole("heading").click();
  await expect(dialog.getByText("Reporting deadline: 14 Sep 2026", { exact: true })).toBeVisible();
  await dialog.getByLabel("Employment type", { exact: true }).selectOption("full_time");
  await dialog.getByLabel("Job title", { exact: true }).fill("Senior carer");
  await dialog.getByLabel("Nationality", { exact: true }).fill("British");
  await dialog.getByLabel("Contact number", { exact: true }).fill("01234567890");
  await dialog.getByLabel("Address", { exact: true }).fill("1 High Street, London");
  await dialog
    .getByLabel("Remarks or restriction to work", { exact: true })
    .fill("Changed working hours and pay");
  await dialog
    .getByRole("checkbox", { name: "Employee told to inform HR promptly", exact: true })
    .check();
  await dialog
    .getByRole("checkbox", {
      name: "Employee told to cooperate with a Home Office interview",
      exact: true,
    })
    .check();
  await dialog.getByRole("checkbox", { name: /^Passport · version 1 / }).check();
  await dialog.getByRole("button", { name: "Save", exact: true }).focus();
  await dialog.getByRole("heading").click();
  expect(saves).toBe(0);
  await audit(page, "Worker change sheet", { modal: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(1);
  await expect(log.getByRole("heading", { name: "Salary reduced", exact: true })).toBeVisible();
  await expect(
    log.getByText("Event 28 Aug 2026 · Deadline 14 Sep 2026", { exact: true }),
  ).toBeVisible();
  await expect(log.getByText("Past deadline", { exact: true })).toBeVisible();
  await log.getByText("Snapshot and documents", { exact: true }).click();
  await expect(log.getByText("Senior carer", { exact: true })).toBeVisible();
  await expect(log.getByText("Passport · version 1", { exact: true })).toBeVisible();
  await log.getByRole("button", { name: "Mark as reported", exact: true }).click();
  const reported = page.getByRole("dialog", { name: "Mark as reported", exact: true });
  await reported.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    reported.getByText("Choose the reporting date and enter the SMS reference.", { exact: true }),
  ).toBeVisible();
  expect(saves).toBe(1);
  await reported.getByLabel("Date reported in SMS", { exact: true }).fill("14 Sep 2026");
  await reported.getByLabel("SMS reference", { exact: true }).fill("SMS-WORKER");
  await reported.getByRole("heading").click();
  expect(saves).toBe(1);
  await reported.getByRole("button", { name: "Save", exact: true }).click();
  await expect(reported).not.toBeVisible();
  expect(saves).toBe(2);
  await expect(
    log.getByText("Reported by Amira Hassan on 14 Sep 2026 · SMS-WORKER", { exact: true }),
  ).toBeVisible();
  await expect(log.getByRole("button", { name: "Mark as reported", exact: true })).toHaveCount(0);
  await log.getByRole("link", { name: "View company-wide changes", exact: true }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Change of circumstances" }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Still to report", exact: true }).click();
  await expect(page.getByRole("heading", { name: "No changes match", exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "All", exact: true }).click();
  await page
    .getByRole("searchbox", { name: "Search changes", exact: true })
    .fill("Nadia SMS-WORKER");
  await expect(
    page
      .getByRole("grid", { name: "Worker changes", exact: true })
      .getByText("Nadia Grant · COC100", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("list", { name: "Worker changes", exact: true })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await audit(page, "Worker change register mobile");
  await context.close();
});

test("Organisation changes calculate twenty days, retain reports and handle prompt reporting", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("orgchanges"));
  const context = await browser.newContext({ storageState: await api.storageState() });
  await api.dispose();
  const page = await context.newPage();
  let saves = 0;
  page.on("request", (request) => {
    if (
      ["POST", "PUT", "DELETE"].includes(request.method()) &&
      request.url().includes("/compliance/org-changes")
    )
      saves++;
  });
  await page.goto("/sponsor-compliance/change-of-circumstances");
  await page.getByRole("tab", { name: "Organisation", exact: true }).click();
  await page.getByRole("button", { name: "Log organisation change", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Log organisation change", exact: true });
  await dialog.getByLabel("Date organisation became aware", { exact: true }).fill("28 Aug 2026");
  await dialog.getByLabel("Remarks", { exact: true }).fill("New office");
  await expect(dialog.getByText("Reporting deadline: 28 Sep 2026", { exact: true })).toBeVisible();
  await dialog.getByRole("heading").click();
  expect(saves).toBe(0);
  await audit(page, "Organisation change sheet", { modal: true });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(1);
  const grid = page.getByRole("grid", { name: "Organisation changes", exact: true });
  await grid.getByText("Address changed", { exact: true }).click();
  const details = page.getByRole("dialog", { name: "Change details", exact: true });
  await details.getByRole("button", { name: "Edit entry", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Edit organisation change", exact: true });
  await dialog.getByLabel("Organisation change type", { exact: true }).selectOption("ownership");
  await dialog.getByLabel("Date organisation became aware", { exact: true }).fill("1 Sep 2026");
  await dialog.getByRole("heading").click();
  await expect(dialog.getByText("Reporting deadline: 29 Sep 2026", { exact: true })).toBeVisible();
  expect(saves).toBe(1);
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(2);
  await grid.getByText("Ownership changed", { exact: true }).click();
  await details.getByRole("button", { name: "Mark as reported", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Mark as reported", exact: true });
  await dialog.getByLabel("Date reported in SMS", { exact: true }).fill("1 Oct 2026");
  await dialog.getByLabel("SMS reference", { exact: true }).fill("SMS-ORG");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(3);
  await expect(grid.getByText("Reported", { exact: true })).toBeVisible();
  await grid.getByText("Ownership changed", { exact: true }).click();
  await expect(details.getByText("Reported after the deadline", { exact: true })).toBeVisible();
  await expect(details.getByRole("button", { name: "Edit entry", exact: true })).toHaveCount(0);
  await expect(details.getByRole("button", { name: "Archive entry", exact: true })).toHaveCount(0);
  await details.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Log organisation change", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Log organisation change", exact: true });
  await dialog
    .getByLabel("Organisation change type", { exact: true })
    .selectOption("ao_or_key_contact");
  await dialog.getByLabel("Date organisation became aware", { exact: true }).fill("28 Aug 2026");
  await dialog.getByRole("heading").click();
  await expect(dialog.getByText("Report promptly", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(4);
  await grid.getByText("Authorising Officer or Key Contact replacement", { exact: true }).click();
  await expect(details.getByText("Report promptly", { exact: true })).toBeVisible();
  await details.getByRole("button", { name: "Archive entry", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Archive organisation entry", exact: true });
  await dialog.getByRole("button", { name: "Archive entry", exact: true }).click();
  await expect(
    dialog.getByText("Enter why this entry should be archived.", { exact: true }),
  ).toBeVisible();
  expect(saves).toBe(4);
  await dialog.getByLabel("Reason for archiving", { exact: true }).fill("Duplicate entry");
  await dialog.getByRole("button", { name: "Archive entry", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(saves).toBe(5);
  await expect(
    grid.getByText("Authorising Officer or Key Contact replacement", { exact: true }),
  ).toHaveCount(0);
  await expect(grid.getByText("Ownership changed", { exact: true })).toBeVisible();
  await audit(page, "Organisation change register");
  await context.close();
});
