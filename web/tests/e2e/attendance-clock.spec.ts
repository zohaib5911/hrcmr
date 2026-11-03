/** T9.3 real clock actions, consent, install assets and reviewed report approvals. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("clock from Home, consent to location, clock out and approve a report's completed week", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const people: string[] = [];
  for (const [i, first] of ["Mina", "Ben"].entries()) {
    const response = await api.post(`${API}/employees`, {
      headers,
      data: {
        first_name: first,
        last_name: "Clock",
        employee_number: `CL${i}`,
        email: `clock${i}@example.com`,
        hire_date: "2025-01-01",
      },
    });
    expect(response.status(), await response.text()).toBe(201);
    people.push((await response.json()).id);
  }
  const membership = (await (await api.get(`${API}/users`)).json()).users.find(
    (u: { is_you: boolean }) => u.is_you,
  );
  const linked = await api.put(`${API}/users/${membership.id}/employee`, {
    headers,
    data: { employee_id: people[0] },
  });
  expect(linked.status(), await linked.text()).toBe(200);
  const assigned = await api.post(`${API}/employees/${people[1]}/assignments`, {
    headers,
    data: {
      employment_type: "full_time",
      effective_from: "2025-01-01",
      reporting_authority_employee_id: people[0],
    },
  });
  expect(assigned.status(), await assigned.text()).toBe(201);
  await page.goto("/dashboard");
  await page.getByRole("link", { name: "Clock in or out", exact: true }).click();
  await expect(page.getByText("You are clocked out.", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("switch", { name: /^Share my location for this action/ }),
  ).toHaveCount(0);
  expect((await (await api.get(`${API}/attendance/clock`)).json()).active).toBeNull();
  const manifest = await context.request.get("http://127.0.0.1:3100/clock/manifest.webmanifest");
  expect(manifest.status()).toBe(200);
  expect(await manifest.json()).toMatchObject({ start_url: "/clock", display: "standalone" });
  for (const size of [192, 512]) {
    const icon = await context.request.get(`http://127.0.0.1:3100/clock/icon?size=${size}`);
    expect(icon.status(), await icon.text()).toBe(200);
    expect(icon.headers()["content-type"]).toContain("image/png");
  }
  await expect
    .poll(() =>
      page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration("/clock"))),
    )
    .toBe(true);
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 51.5007, longitude: -0.1246, accuracy: 25 });
  const enabled = await api.patch(`${API}/company`, {
    headers,
    data: { clock_geolocation_enabled: true },
  });
  expect(enabled.status(), await enabled.text()).toBe(200);
  await page.reload();
  await page.getByRole("switch", { name: /^Share my location for this action/ }).click();
  await page.getByLabel("Clock note (optional)", { exact: true }).fill("Reception cover");
  await page.getByRole("button", { name: "Clock in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Clock out", exact: true })).toBeVisible();
  await expect(
    page.getByRole("switch", { name: /^Share my location for this action/ }),
  ).not.toBeChecked();
  await page.reload();
  await expect(page.getByRole("button", { name: "Clock out", exact: true })).toBeVisible();
  await page.getByLabel("Unpaid break (minutes)", { exact: true }).fill("0");
  await page.getByRole("button", { name: "Clock out", exact: true }).click();
  await expect(page.getByText(/Clocked out · .* hours recorded/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Clock mobile");

  const recorded = await api.put(`${API}/attendance-records`, {
    headers,
    data: {
      employee_id: people[1],
      date: "2026-01-05",
      status: "present",
      clock_in: "09:00",
      clock_out: "17:00",
      unpaid_break_minutes: 30,
    },
  });
  expect(recorded.status(), await recorded.text()).toBe(200);
  await page.goto("/attendance/timesheets");
  await page.getByLabel("Timesheet week containing", { exact: true }).fill("2026-01-05");
  await page.getByRole("button", { name: "Review Ben Clock", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Ben Clock timesheet", exact: true });
  await expect(sheet.getByText("Needs review", { exact: true })).toBeVisible();
  await sheet.getByRole("button", { name: "Approve timesheet", exact: true }).click();
  await sheet.getByRole("button", { name: "Confirm approval", exact: true }).click();
  await expect(sheet.getByText("Approved", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await audit(page, "Report timesheets mobile");
  const changed = await api.put(`${API}/attendance-records`, {
    headers,
    data: {
      employee_id: people[1],
      date: "2026-01-05",
      status: "present",
      clock_in: "09:00",
      clock_out: "18:00",
      unpaid_break_minutes: 30,
    },
  });
  expect(changed.status(), await changed.text()).toBe(200);
  await page.getByRole("button", { name: "Reload timesheets", exact: true }).click();
  await page.getByRole("button", { name: "Review Ben Clock", exact: true }).click();
  await expect(sheet.getByText("Needs review", { exact: true })).toBeVisible();
  await expect(sheet.getByText(/8.50 hours/).first()).toBeVisible();
});
