/** T9.1 real manual upsert, hours/KPIs, ranges/filters, profile history and protected leave. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("record and update attendance, filter ranges, inspect profile and protect approved leave", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const person = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Harper",
      last_name: "Patel",
      email: "harper@example.com",
      employee_number: "ATT1",
      hire_date: "2025-01-01",
    },
  });
  expect(person.status(), await person.text()).toBe(201);
  const id = (await person.json()).id as string;
  await page.goto("/attendance");
  await expect(
    page.getByRole("heading", { level: 1, name: "Attendance", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Selected day", { exact: true }).fill("2026-11-03");
  await page.getByRole("button", { name: "Record attendance", exact: true }).click();
  const form = page.getByRole("dialog", { name: "Record attendance", exact: true });
  await form.getByLabel("Employee", { exact: true }).selectOption(id);
  await form.getByLabel("Date", { exact: true }).fill("2026-11-03");
  await form.getByLabel("Clock in", { exact: true }).fill("09:00");
  await form.getByLabel("Clock out", { exact: true }).fill("17:00");
  await form.getByLabel("Unpaid break (minutes)", { exact: true }).fill("30");
  await form.getByLabel("Note (optional)", { exact: true }).fill("Front desk");
  await form.getByRole("button", { name: "Save attendance", exact: true }).click();
  await expect(form).toBeHidden();
  const records = page.getByRole("grid", { name: "Attendance records", exact: true });
  await expect(records.getByRole("gridcell", { name: "7.5", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit record", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "Edit attendance", exact: true });
  await expect(edit.getByLabel("Employee", { exact: true })).toBeDisabled();
  await edit.getByLabel("Status", { exact: true }).selectOption("late");
  await edit.getByLabel("Clock out", { exact: true }).fill("18:00");
  await edit.getByRole("button", { name: "Save attendance", exact: true }).click();
  await expect(edit).toBeHidden();
  await expect(records.getByRole("gridcell", { name: "8.5", exact: true })).toBeVisible();
  await expect(
    page
      .locator("p")
      .filter({ hasText: /^Late$/ })
      .locator("..")
      .getByText("1", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Attendance status", { exact: true }).selectOption("absent");
  await expect(page.getByText("No attendance recorded", { exact: true })).toBeVisible();
  await page.getByLabel("Attendance status", { exact: true }).selectOption("all");
  for (const range of ["Week", "Month", "Custom"]) {
    await page.getByRole("radio", { name: range, exact: true }).click();
    if (range === "Custom") {
      await page.getByLabel("Start date", { exact: true }).fill("2026-11-01");
      await page.getByLabel("End date", { exact: true }).fill("2026-11-30");
    }
    await expect(records.getByText("Harper Patel", { exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "Record attendance", exact: true }).click();
  const sick = page.getByRole("dialog", { name: "Record attendance", exact: true });
  await sick.getByLabel("Employee", { exact: true }).selectOption(id);
  await sick.getByLabel("Date", { exact: true }).fill("2026-11-04");
  await sick.getByLabel("Status", { exact: true }).selectOption("sick");
  await expect(sick.getByLabel("Clock in", { exact: true })).toHaveCount(0);
  await sick.getByRole("button", { name: "Save attendance", exact: true }).click();
  await expect(sick).toBeHidden();
  await page.goto(`/employees/${id}?tab=attendance`);
  await page.getByLabel("Month", { exact: true }).fill("2026-11");
  await expect(
    page
      .getByRole("grid", { name: "Attendance records", exact: true })
      .getByText("Sick", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Month", { exact: true }).fill("2026-10");
  await expect(page.getByText("No attendance recorded", { exact: true })).toBeVisible();
  const kinds = await (await api.get(`${API}/leave/types`)).json();
  const annual = kinds.find((t: { seed_key: string }) => t.seed_key === "annual");
  const leave = await api.post(`${API}/leave/requests`, {
    headers,
    data: {
      employee_id: id,
      leave_type_id: annual.id,
      start_date: "2026-11-05",
      end_date: "2026-11-05",
    },
  });
  expect(leave.status(), await leave.text()).toBe(201);
  const approved = await api.post(`${API}/leave/requests/${(await leave.json()).id}/approve`, {
    headers,
    data: {},
  });
  expect(approved.status(), await approved.text()).toBe(200);
  await page.goto(`/attendance?employee_id=${id}&month=2026-11`);
  await expect(page.getByRole("radio", { name: "Month", exact: true })).toBeChecked();
  await expect(page.getByLabel("Employee", { exact: true })).toHaveValue(id);
  await page.getByRole("button", { name: "View record", exact: true }).click();
  await expect(page.getByRole("dialog").getByText(/protected from manual edits/)).toBeVisible();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Save attendance", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Attendance workspace mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});

test("a repeated clock-change hour is reviewed explicitly", async ({ page, context }) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const person = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Rory",
      last_name: "Clock",
      email: "rory@example.com",
      employee_number: "ATT-DST",
      hire_date: "2025-01-01",
    },
  });
  expect(person.status(), await person.text()).toBe(201);
  const id = (await person.json()).id as string;
  await page.goto("/attendance");
  await page.getByLabel("Selected day", { exact: true }).fill("2026-10-25");
  await page.getByRole("button", { name: "Record attendance", exact: true }).click();
  const form = page.getByRole("dialog", { name: "Record attendance", exact: true });
  await form.getByLabel("Employee", { exact: true }).selectOption(id);
  await form.getByLabel("Date", { exact: true }).fill("2026-10-25");
  await form.getByLabel("Clock in", { exact: true }).fill("01:30");
  await form.getByLabel("Clock out", { exact: true }).fill("03:00");
  await form.getByRole("button", { name: "Save attendance", exact: true }).click();
  await form.getByLabel("Clock-in repeated hour", { exact: true }).selectOption("1");
  await form.getByRole("button", { name: "Save attendance", exact: true }).click();
  await expect(form).toBeHidden();
  await expect(
    page
      .getByRole("grid", { name: "Attendance records", exact: true })
      .getByRole("gridcell", { name: "1.5", exact: true }),
  ).toBeVisible();
});
