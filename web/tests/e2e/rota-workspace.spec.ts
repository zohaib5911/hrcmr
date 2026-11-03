/** T9.5 real quick-add/edit, publication snapshots, copy/clear menus and private print. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("plan shifts, publish to My Shifts, copy scoped weeks and clear only after confirmation", async ({
  page,
  context,
}) => {
  test.setTimeout(60_000);
  const api = context.request;
  const headers = await csrfHeaders(api);
  const people: string[] = [];
  for (const [i, name] of ["Alex", "Ben"].entries()) {
    const response = await api.post(`${API}/employees`, {
      headers,
      data: {
        first_name: name,
        last_name: "Rota",
        employee_number: `RO${i}`,
        email: `rota${i}@example.com`,
        hire_date: "2025-01-01",
      },
    });
    expect(response.status(), await response.text()).toBe(201);
    people.push((await response.json()).id);
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
  const template = await api.post(`${API}/rota/shift-types`, {
    headers,
    data: {
      name: "Day",
      starts_at: "09:00",
      ends_at: "17:00",
      break_start: "12:00",
      break_end: "12:30",
    },
  });
  expect(template.status(), await template.text()).toBe(201);
  async function grid(week = "2026-11-02") {
    return await (await api.get(`${API}/rota/weeks/${week}`)).json();
  }
  await page.goto("/rota?week=2026-11-02");
  await expect(
    page.getByText("Draft rota — not visible to employees yet", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("group", { name: "Quick add shift types", exact: true })
    .getByRole("button", { name: "Day", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add shift for Alex Rota, 2 Nov 2026", exact: true })
    .click();
  await expect.poll(async () => (await grid()).shifts.length).toBe(1);
  await page
    .getByRole("button", { name: "Add shift for Alex Rota, 3 Nov 2026", exact: true })
    .click();
  await expect.poll(async () => (await grid()).shifts.length).toBe(2);
  await page
    .getByRole("group", { name: "Quick add shift types", exact: true })
    .getByRole("button", { name: "Day", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add shift for Alex Rota, 4 Nov 2026", exact: true })
    .click();
  const add = page.getByRole("dialog", { name: "Add shift", exact: true });
  await add.getByLabel("Shift type (optional)", { exact: true }).selectOption({ label: "Day" });
  await add.getByRole("combobox", { name: "Employee", exact: true }).fill("Ben");
  await page.getByRole("option", { name: /Ben Rota/ }).click();
  await add.getByRole("button", { name: "Save shift", exact: true }).click();
  await expect(add).toBeHidden();
  await expect.poll(async () => (await grid()).shifts.length).toBe(3);
  const row = page
    .getByRole("region", { name: "Weekly rota", exact: true })
    .getByRole("row")
    .filter({ has: page.getByText("Alex Rota", { exact: true }) });
  await row.getByText("09:00–17:00", { exact: true }).first().click();
  const edit = page.getByRole("dialog", { name: "Edit shift", exact: true });
  await edit.getByLabel("Finishes", { exact: true }).fill("17:30");
  await edit.getByLabel("Shift note (optional)", { exact: true }).fill("Reception cover");
  await edit.getByRole("button", { name: "Save shift", exact: true }).click();
  await expect(edit).toBeHidden();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Print rota PDF", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("rota-2026-11-02.pdf");
  await page.goto("/my-shifts?week=2026-11-02");
  await expect(page.getByText("No published shifts this week.", { exact: true })).toBeVisible();
  await page.goto("/rota?week=2026-11-02");
  await page.getByRole("button", { name: "Publish week", exact: true }).click();
  await page.getByRole("button", { name: "Confirm publication", exact: true }).click();
  await expect(page.getByText("Rota published", { exact: true })).toBeVisible();
  await page.goto("/my-shifts?week=2026-11-02");
  await expect(page.getByText("Reception cover", { exact: true })).toBeVisible();
  expect(
    (await (await api.get(`${API}/rota/own?start=2026-11-02&end=2026-11-08`)).json()).shifts,
  ).toHaveLength(2);
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "My shifts mobile");
  await page.goto("/rota?week=2026-11-02");
  await row.getByText("09:00–17:30", { exact: true }).click();
  await edit.getByLabel("Finishes", { exact: true }).fill("18:00");
  await edit.getByRole("button", { name: "Save shift", exact: true }).click();
  await expect(edit).toBeHidden();
  await expect(page.getByText("Changes not published", { exact: true })).toBeVisible();
  expect(
    (await (await api.get(`${API}/rota/own?start=2026-11-02&end=2026-11-08`)).json()).shifts[0]
      .ends_local,
  ).toBe("17:30");
  await page.getByRole("button", { name: "Next week", exact: true }).click();
  await page.getByRole("button", { name: "Copy last week", exact: true }).click();
  await page.getByRole("button", { name: "Confirm changes", exact: true }).click();
  await expect.poll(async () => (await grid("2026-11-09")).shifts.length).toBe(3);
  await page.getByRole("button", { name: "Actions for 9 Nov 2026", exact: true }).click();
  await page.getByRole("menuitem", { name: "Copy to the rest of Mon–Fri", exact: true }).click();
  await page.getByRole("button", { name: "Confirm changes", exact: true }).click();
  await expect.poll(async () => (await grid("2026-11-09")).shifts.length).toBe(5);
  await page.getByRole("button", { name: "Actions for 9 Nov 2026", exact: true }).click();
  await page.getByRole("menuitem", { name: "Copy to every other day", exact: true }).click();
  await page.getByRole("button", { name: "Confirm changes", exact: true }).click();
  await expect.poll(async () => (await grid("2026-11-09")).shifts.length).toBe(7);
  await expect(page.getByText(/planned hours exceeds 48 hours/)).toBeVisible();
  await audit(page, "Rota grid mobile");
  await page.getByRole("button", { name: "Actions for Alex Rota", exact: true }).click();
  await page.getByRole("menuitem", { name: "Clear their week", exact: true }).click();
  await page.getByRole("button", { name: "Confirm changes", exact: true }).click();
  await expect.poll(async () => (await grid("2026-11-09")).shifts.length).toBe(0);
  await page.getByRole("button", { name: "Previous week", exact: true }).click();
  await page.getByRole("button", { name: "Week actions", exact: true }).click();
  await page.getByRole("menuitem", { name: "Clear this whole week", exact: true }).click();
  expect((await grid()).shifts).toHaveLength(3);
  await page.getByRole("button", { name: "Confirm changes", exact: true }).click();
  await expect.poll(async () => (await grid()).shifts.length).toBe(0);
  expect(
    (await (await api.get(`${API}/rota/own?start=2026-11-02&end=2026-11-08`)).json()).shifts,
  ).toHaveLength(2);
  await page.getByRole("button", { name: "Publish week", exact: true }).click();
  await page.getByRole("button", { name: "Confirm publication", exact: true }).click();
  await expect(page.getByText("Rota published", { exact: true })).toBeVisible();
  expect(
    (await (await api.get(`${API}/rota/own?start=2026-11-02&end=2026-11-08`)).json()).shifts,
  ).toHaveLength(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
