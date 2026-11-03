/** T9.2 scanned files, reviewed import, atomic bulk statuses and downloadable reports. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("preview row errors, import a corrected file, bulk edit and export monthly absences", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const person = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Alex",
      last_name: "Import",
      email: "alex-import@example.com",
      employee_number: "IMP1",
      hire_date: "2025-01-01",
    },
  });
  expect(person.status(), await person.text()).toBe(201);
  const id = (await person.json()).id as string;
  await page.goto("/attendance");
  await page.getByRole("link", { name: "Import", exact: true }).click();
  const templateDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Excel template", exact: true }).click();
  expect((await templateDownload).suggestedFilename()).toBe("attendance-template.xlsx");
  const header = "employee_number,date,status,clock_in,clock_out,note\n";
  await page.getByLabel("Attendance spreadsheet", { exact: true }).setInputFiles({
    name: "invalid.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(header + "UNKNOWN,2026-11-03,Present,09:00,17:00,Front desk\n"),
  });
  await page.getByRole("button", { name: "Preview import", exact: true }).click();
  await expect(page.getByText("0 of 1 rows valid", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Commit import", exact: true })).toBeDisabled();
  expect(
    (await (await api.get(`${API}/attendance-records?start=2026-11-03&end=2026-11-03`)).json())
      .items,
  ).toHaveLength(0);
  await page.getByLabel("Attendance spreadsheet", { exact: true }).setInputFiles({
    name: "attendance.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      header + "IMP1,2026-11-03,Present,09:00,17:00,Front desk\nIMP1,2026-11-04,Sick,,,Rest\n",
    ),
  });
  await page.getByRole("button", { name: "Preview import", exact: true }).click();
  await expect(page.getByText("2 of 2 rows valid", { exact: false })).toBeVisible();
  await expect(page).toHaveURL(/preview=/);
  await page.reload();
  await expect(page.getByText("2 of 2 rows valid", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "View row 2", exact: true }).click();
  await expect(page.getByRole("dialog").getByText("Front desk", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Commit import", exact: true }).click();
  await page.getByRole("button", { name: "Save records", exact: true }).click();
  await expect(page.getByText("Attendance imported", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Attendance imported", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Attendance import mobile");
  await page.goto("/attendance/bulk");
  await page.getByLabel("Week containing", { exact: true }).fill("2026-11-02");
  const tuesday = page.getByRole("combobox", { name: "Alex Import, 3 Nov 2026", exact: true });
  await expect(tuesday).toHaveValue("present");
  await tuesday.selectOption("late");
  await page
    .getByRole("combobox", { name: "Alex Import, 5 Nov 2026", exact: true })
    .selectOption("absent");
  await expect(page.getByRole("button", { name: "Next week", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Save 2 changes", exact: true }).click();
  await expect(page.getByText("2 attendance records saved", { exact: true })).toBeVisible();
  const records = (
    await (await api.get(`${API}/attendance-records?start=2026-11-03&end=2026-11-05`)).json()
  ).items;
  const updated = records.find((r: { date: string }) => r.date === "2026-11-03");
  expect(updated).toMatchObject({
    employee_id: id,
    status: "late",
    hours: "8.00",
    note: "Front desk",
    source: "grid",
  });
  await audit(page, "Bulk attendance mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.goto("/attendance/absences?month=2026-11");
  const table = page.getByRole("grid", { name: "Monthly absences", exact: true });
  await expect(table.getByText("Sick", { exact: true })).toBeVisible();
  await expect(table.getByText("Absent", { exact: true })).toBeVisible();
  for (const kind of ["Excel", "PDF"]) {
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: `Export ${kind}`, exact: true }).click();
    expect((await download).suggestedFilename()).toBe(
      `absences-2026-11-01-2026-11-30.${kind === "Excel" ? "xlsx" : "pdf"}`,
    );
  }
  await audit(page, "Monthly absences mobile");
  await page.getByLabel("Absence month", { exact: true }).fill("2026-10");
  await expect(table.getByText("Sick", { exact: true })).toHaveCount(0);
});
