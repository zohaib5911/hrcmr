/** T7.4: explicit review actions, sender history and a received in-app message. */
import { request as playwrightRequest } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const expiry = (days: number) =>
  new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

test("Reminder review saves and snoozes explicitly, sends once and keeps received/history messages", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("reminders"));
  const headers = await csrfHeaders(api);
  const employee = await api.post(API + "/employees", {
    headers,
    data: {
      first_name: "Kai",
      last_name: "Reed",
      email: "kai@example.com",
      employee_number: "REM100",
      hire_date: "2025-01-06",
    },
  });
  expect(employee.status(), await employee.text()).toBe(201);
  const { id } = (await employee.json()) as { id: string };
  const passport = await api.post(API + "/employees/" + id + "/sponsor-documents", {
    headers,
    data: {
      doc_type: "passport",
      reference_number: "PRIVATE-PASSPORT-123",
      expiry_date: expiry(21),
    },
  });
  expect(passport.status(), await passport.text()).toBe(201);
  const visa = await api.post(API + "/employees/" + id + "/sponsor-documents", {
    headers,
    data: { doc_type: "visa", visa_route: "skilled_worker", expiry_date: expiry(120) },
  });
  expect(visa.status(), await visa.text()).toBe(201);
  const context = await browser.newContext({ storageState: await api.storageState() });
  const page = await context.newPage();
  let drafts = 0;
  let snoozes = 0;
  let sends = 0;
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "PATCH" && /\/reminders\//.test(path)) drafts++;
    if (request.method() === "POST" && path.endsWith("/snooze")) snoozes++;
    if (request.method() === "POST" && path.endsWith("/send")) sends++;
  });
  await page.goto("/sponsor-compliance/reminders");
  await expect(page.getByRole("heading", { level: 1, name: "Compliance reminders" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Due now (1)", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Review & send", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Review reminder", exact: true });
  const message = dialog.getByRole("textbox", { name: "Message for employee", exact: true });
  await expect(message).toBeEnabled();
  await expect(dialog.getByText("Drafted, not sent", { exact: true })).toBeVisible();
  await expect(dialog.getByText("Employee account not linked", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Send reminder", exact: true })).toBeDisabled();
  await message.fill("Please arrange your renewed passport with HR.");
  await dialog.getByRole("heading").click();
  expect(drafts).toBe(0);
  expect(sends).toBe(0);
  await dialog.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(page.getByText("Draft saved", { exact: true })).toBeVisible();
  expect(drafts).toBe(1);
  expect(sends).toBe(0);
  await dialog.getByRole("button", { name: "Close review", exact: true }).click();
  const people = (await api.get(API + "/users")).json();
  const users = (await people) as { users: { id: string; is_you: boolean }[] };
  const membership = users.users.find((user) => user.is_you)!;
  const linked = await api.put(API + "/users/" + membership.id + "/employee", {
    headers: await csrfHeaders(api),
    data: { employee_id: id },
  });
  expect(linked.status(), await linked.text()).toBe(200);
  await page.reload();
  await page.getByRole("button", { name: "Review & send", exact: true }).click();
  await expect(message).toHaveValue("Please arrange your renewed passport with HR.");
  await expect(message).toBeEnabled();
  await expect(dialog.getByRole("button", { name: "Send reminder", exact: true })).toBeEnabled();
  await message.fill("Please share your updated passport with HR.");
  await dialog.getByRole("heading").click();
  expect(sends).toBe(0);
  await audit(page, "Reminder review sheet", { modal: true });
  await dialog.getByRole("button", { name: "Not now (7 days)", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(snoozes).toBe(1);
  expect(sends).toBe(0);
  await expect(page.getByRole("tab", { name: "Due now (0)", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No reminders due", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Document register", exact: true }).click();
  await page.getByRole("tab", { name: "Passport", exact: true }).click();
  await page.getByRole("button", { name: "30 days · Snoozed", exact: true }).click();
  await expect(message).toHaveValue("Please share your updated passport with HR.");
  await expect(message).toBeEnabled();
  await expect(dialog.getByText(/^Snoozed until /)).toBeVisible();
  await dialog.getByRole("heading").click();
  expect(sends).toBe(0);
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/send") && r.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Send reminder", exact: true }).click();
  const sent = await response;
  expect(sent.status(), await sent.text()).toBe(200);
  const sentRecord = (await sent.json()) as { id: string };
  await expect(dialog).not.toBeVisible();
  expect(sends).toBe(1);
  await page.getByRole("tab", { name: "History (1)", exact: true }).click();
  const history = page.getByRole("grid", { name: "Sent reminder history", exact: true });
  await expect(history.getByText("Amira Hassan", { exact: true })).toBeVisible();
  await expect(history.getByText("Email queued", { exact: true })).toBeVisible();
  await history.getByText("Kai Reed", { exact: true }).dblclick();
  await expect(dialog.getByText(/^Sent by Amira Hassan on /)).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Send reminder", exact: true })).toHaveCount(0);
  await expect(
    dialog.getByText("Please share your updated passport with HR.", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close review", exact: true }).click();
  await page.getByRole("button", { name: /^Notifications/ }).click();
  const bell = page.getByRole("dialog", { name: "Notifications", exact: true });
  await expect(bell.getByRole("region", { name: "Needs attention" })).toBeVisible();
  await expect(
    bell.getByText("Please share your updated passport with HR.", { exact: true }),
  ).toBeVisible();
  await bell.getByRole("button", { name: "Mark all read", exact: true }).click();
  await expect(bell.getByText("· Unread", { exact: true })).toHaveCount(0);
  await expect(bell.getByRole("region", { name: "Needs attention" })).toBeVisible();
  await bell.getByRole("link", { name: /Open message/ }).click();
  await expect(page).toHaveURL("/my-documents?reminder=" + sentRecord.id);
  await page.goto("/my-documents?reminder=" + sentRecord.id);
  await expect(page.getByRole("heading", { level: 1, name: "My documents" })).toBeVisible();
  const received = page.getByRole("article", { name: "Passport reminder", exact: true });
  await expect(
    received.getByText("Please share your updated passport with HR.", { exact: true }),
  ).toBeVisible();
  await expect(received).toBeFocused();
  await expect(page.getByText("PRIVATE-PASSPORT-123", { exact: true })).toHaveCount(0);
  await audit(page, "Received reminder");
  await page.goto("/sponsor-compliance/reminders");
  await page.getByRole("tab", { name: "Document register", exact: true }).click();
  await page.getByRole("tab", { name: "Visa", exact: true }).click();
  await page.getByRole("button", { name: "90 days · Scheduled", exact: true }).click();
  await expect(message).toBeEnabled();
  await expect(dialog.getByRole("button", { name: "Send reminder", exact: true })).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Not now (7 days)", exact: true })).toHaveCount(
    0,
  );
  await dialog.getByRole("button", { name: "Close review", exact: true }).click();
  await page.getByRole("tab", { name: "Passport", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("list", { name: "Reminder document register", exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await audit(page, "Reminder register mobile");
  await api.dispose();
  await context.close();
});
