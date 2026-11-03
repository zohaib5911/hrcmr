/** Phase 9 gate: attendance, rota and work log at 390/1280 px in light/dark. */
import path from "node:path";
import { request, type Page } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-9");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");
// Independent companies keep the four visual states identical instead of accumulating seed data.
test.use({
  storageState: async ({}, use) => {
    const api = await request.newContext();
    try {
      await createSignedInAdmin(api);
      // eslint-disable-next-line react-hooks/rules-of-hooks -- Playwright fixture callback.
      await use(await api.storageState());
    } finally {
      await api.dispose();
    }
  },
});

async function shoot(page: Page, name: string, modal = false) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  await audit(page, name, { modal });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: !modal,
    animations: "disabled",
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`Time and work at ${width}px`, async ({ page, context }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const api = context.request;
        const headers = await csrfHeaders(api);
        const people: string[] = [];
        for (const [i, name] of ["Mina", "Ben", "Clara"].entries()) {
          const made = await api.post(`${API}/employees`, {
            headers,
            data: {
              first_name: name,
              last_name: "Patel",
              employee_number: `TIME${i}`,
              email: `time${i}@example.com`,
              hire_date: "2025-01-01",
            },
          });
          expect(made.status(), await made.text()).toBe(201);
          people.push((await made.json()).id);
        }
        const member = (await (await api.get(`${API}/users`)).json()).users.find(
          (u: { is_you: boolean }) => u.is_you,
        );
        expect(
          (
            await api.put(`${API}/users/${member.id}/employee`, {
              headers,
              data: { employee_id: people[0] },
            })
          ).status(),
        ).toBe(200);
        const browserDay = new Date().toISOString().slice(0, 10);
        const day = (
          await (await api.get(`${API}/work-log/own?start=${browserDay}&end=${browserDay}`)).json()
        ).today as string;
        const mondayDate = new Date(`${day}T12:00:00Z`);
        mondayDate.setUTCDate(mondayDate.getUTCDate() - ((mondayDate.getUTCDay() + 6) % 7));
        const week = mondayDate.toISOString().slice(0, 10);
        const department = (
          await (
            await api.post(`${API}/departments`, { headers, data: { name: "Customer care" } })
          ).json()
        ).id;
        const designation = (
          await (
            await api.post(`${API}/designations`, {
              headers,
              data: { title: "Coordinator", department_id: department },
            })
          ).json()
        ).id;
        expect(
          (
            await api.post(`${API}/employees/${people[1]}/assignments`, {
              headers,
              data: {
                employment_type: "full_time",
                effective_from: "2025-01-01",
                reporting_authority_employee_id: people[0],
                department_id: department,
                designation_id: designation,
              },
            })
          ).status(),
        ).toBe(201);
        const templates: string[] = [];
        for (const [name, starts_at, ends_at] of [
          ["Day", "09:00", "17:00"],
          ["Night", "22:00", "06:00"],
        ]) {
          const made = await api.post(`${API}/rota/shift-types`, {
            headers,
            data: { name, starts_at, ends_at, description: "Customer support coverage" },
          });
          expect(made.status(), await made.text()).toBe(201);
          templates.push((await made.json()).id);
        }
        const scope = {
          department_id: department,
          designation_id: designation,
          shift_type_id: templates[0],
        };
        expect(
          (
            await api.post(`${API}/rota/late-policies`, {
              headers,
              data: {
                ...scope,
                grace_minutes: 5,
                allowed_late_days_per_month: 2,
                deduction_type: "none",
                deduction_value: "0",
              },
            })
          ).status(),
        ).toBe(201);
        expect(
          (
            await api.post(`${API}/rota/day-off-patterns`, {
              headers,
              data: { ...scope, weekdays_off: [6, 7], works_public_holidays: false },
            })
          ).status(),
        ).toBe(201);
        for (const [i, employee] of people.entries()) {
          const date = new Date(`${week}T12:00:00Z`);
          date.setUTCDate(date.getUTCDate() + i);
          const made = await api.post(`${API}/rota/scheduled-shifts`, {
            headers,
            data: {
              employee_id: employee,
              date: date.toISOString().slice(0, 10),
              starts_at: i === 2 ? "22:00" : "09:00",
              ends_at: i === 2 ? "06:00" : "17:00",
              unpaid_break_minutes: 30,
              shift_type_id: templates[i === 2 ? 1 : 0],
              note: "Reception cover",
              version: i,
            },
          });
          expect(made.status(), await made.text()).toBe(201);
        }
        expect(
          (
            await api.post(`${API}/rota/weeks/${week}/publish`, { headers, data: { version: 3 } })
          ).status(),
        ).toBe(200);
        for (const record of [
          {
            employee_id: people[1],
            date: day,
            status: "present",
            clock_in: "09:00",
            clock_out: "17:00",
            unpaid_break_minutes: 30,
          },
          { employee_id: people[2], date: day, status: "sick" },
          {
            employee_id: people[1],
            date: "2026-01-05",
            status: "present",
            clock_in: "09:00",
            clock_out: "17:00",
            unpaid_break_minutes: 30,
          },
        ]) {
          expect(
            (await api.put(`${API}/attendance-records`, { headers, data: record })).status(),
          ).toBe(200);
        }
        const responsibility = (
          await (
            await api.post(`${API}/employees/${people[0]}/responsibilities`, {
              headers,
              data: { text: "Coordinate customer handovers", sort: 0 },
            })
          ).json()
        ).id;
        const entry = await api.post(`${API}/work-log/own`, {
          headers,
          data: {
            date: day,
            from_time: "09:00",
            to_time: "12:00",
            responsibility_id: responsibility,
            description: "Completed daily reception checks and handover notes.",
          },
        });
        expect(entry.status(), await entry.text()).toBe(201);
        const original = await entry.json();
        expect(
          (
            await api.post(`${API}/work-log/${original.id}/correct`, {
              headers,
              data: {
                date: day,
                from_time: "09:00",
                to_time: "12:30",
                responsibility_id: responsibility,
                description: "Reviewed daily reception checks and handover notes.",
                revision: original.revision,
                reason: "Finishing time confirmed with employee",
              },
            })
          ).status(),
        ).toBe(200);
        expect(
          (
            await api.patch(`${API}/company`, {
              headers,
              data: { clock_geolocation_enabled: true },
            })
          ).status(),
        ).toBe(200);
        expect(
          (
            await api.post(`${API}/attendance/clock-in`, {
              headers,
              data: { note: "Reception shift" },
            })
          ).status(),
        ).toBe(200);

        await page.goto("/attendance");
        await expect(
          page.getByRole("button", { name: "Record attendance", exact: true }),
        ).toBeVisible();
        await expect(
          page
            .getByRole("region", { name: "Attendance workspace", exact: true })
            .getByLabel("Employee", { exact: true }),
        ).toContainText("Ben Patel");
        await page.getByRole("textbox", { name: "Selected day", exact: true }).fill(day);
        await expect(
          page
            .getByRole(width === 390 ? "list" : "grid", { name: "Attendance records", exact: true })
            .getByText("Sick", { exact: true }),
        ).toBeVisible();
        await shoot(page, `attendance-${suffix}`);
        await page.getByRole("button", { name: "Record attendance", exact: true }).click();
        await expect(
          page.getByRole("dialog", { name: "Record attendance", exact: true }),
        ).toBeVisible();
        await shoot(page, `attendance-record-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.goto("/attendance/import");
        const templateDownload = page.waitForEvent("download");
        await page.getByRole("button", { name: "Download CSV template", exact: true }).click();
        await templateDownload;
        await page.getByLabel(/Attendance spreadsheet/).setInputFiles({
          name: "attendance-preview.csv",
          mimeType: "text/csv",
          buffer: Buffer.from(
            `employee_number,date,status,clock_in,clock_out,note\nTIME1,${day},Present,09:00,17:00,Reception\nUNKNOWN,${day},Present,09:00,17:00,Check employee number\n`,
          ),
        });
        await page.getByRole("button", { name: "Preview import", exact: true }).click();
        await expect(page.getByText("1 of 2 rows valid", { exact: false })).toBeVisible();
        await shoot(page, `attendance-import-${suffix}`);
        await page.goto("/attendance/bulk");
        await expect(
          page.getByRole("region", { name: "Weekly attendance grid", exact: true }),
        ).toBeVisible();
        await shoot(page, `attendance-bulk-${suffix}`);
        await page.goto(`/attendance/absences?month=${day.slice(0, 7)}`);
        await expect(page.getByText("Sick", { exact: true }).first()).toBeVisible();
        await shoot(page, `attendance-absences-${suffix}`);
        await page.goto("/clock");
        await expect(page.getByRole("button", { name: "Clock out", exact: true })).toBeVisible();
        await shoot(page, `clock-${suffix}`);
        await page.goto("/attendance/timesheets");
        await expect(
          page.getByRole("button", { name: "Review Ben Patel", exact: true }),
        ).toBeVisible();
        await page.getByLabel("Timesheet week containing", { exact: true }).fill("2026-01-05");
        await expect(
          page
            .getByRole(width === 390 ? "list" : "grid", { name: "Report timesheets", exact: true })
            .getByText("7.50", { exact: true }),
        ).toBeVisible();
        await expect(
          page.getByRole("button", { name: "Review Ben Patel", exact: true }),
        ).toBeVisible();
        await shoot(page, `timesheets-${suffix}`);
        await page.getByRole("button", { name: "Review Ben Patel", exact: true }).click();
        await expect(
          page.getByRole("dialog", { name: "Ben Patel timesheet", exact: true }),
        ).toBeVisible();
        await shoot(page, `timesheet-review-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.goto("/rota/settings");
        await expect(page.getByRole("button", { name: "Edit Day", exact: true })).toBeVisible();
        await shoot(page, `rota-settings-${suffix}`);
        await page.getByRole("button", { name: "Edit Day", exact: true }).click();
        await expect(
          page.getByRole("dialog", { name: "Edit shift type", exact: true }),
        ).toBeVisible();
        await shoot(page, `shift-template-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.getByRole("radio", { name: "Late policy", exact: true }).click();
        await shoot(page, `late-policy-${suffix}`);
        await page.getByRole("radio", { name: "Day off patterns", exact: true }).click();
        await shoot(page, `day-off-pattern-${suffix}`);
        await page.goto(`/rota?week=${week}`);
        await expect(page.getByText("Published rota", { exact: true })).toBeVisible();
        await shoot(page, `rota-${suffix}`);
        await page
          .getByRole("button", { name: /Add shift for Mina Patel/ })
          .last()
          .click();
        await expect(page.getByRole("dialog", { name: "Add shift", exact: true })).toBeVisible();
        await shoot(page, `rota-shift-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.goto(`/my-shifts?week=${week}`);
        await expect(page.getByText("Reception cover", { exact: true })).toBeVisible();
        await shoot(page, `my-shifts-${suffix}`);
        await page.goto("/my-work-log");
        await expect(
          page.getByText("Reviewed daily reception checks and handover notes.", { exact: true }),
        ).toBeVisible();
        await shoot(page, `my-work-log-${suffix}`);
        await page.goto("/work-log");
        await expect(
          page.getByRole("button", { name: "Correct entry", exact: true }),
        ).toBeVisible();
        await shoot(page, `work-log-${suffix}`);
        await page.getByRole("button", { name: "Correct entry", exact: true }).click();
        await expect(
          page.getByRole("dialog", { name: "Correct work log", exact: true }),
        ).toBeVisible();
        await shoot(page, `work-log-correct-${suffix}`, true);
        await page.keyboard.press("Escape");
        if (width === 390) await page.getByRole("button", { name: /^Open / }).click();
        else
          await page
            .getByRole("grid", { name: "Work log entries", exact: true })
            .getByText("Reviewed daily reception checks and handover notes.", { exact: true })
            .dblclick();
        await expect(
          page.getByRole("dialog", { name: "Work log entry", exact: true }),
        ).toBeVisible();
        await shoot(page, `work-log-original-${suffix}`, true);
      });
    }
  });
}
