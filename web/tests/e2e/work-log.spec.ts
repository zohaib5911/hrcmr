/** T9.6 own work, same-day editing, original-preserving correction and soft removal. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("record daily work, edit today, correct with a reason and retain removed history", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const person = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Amira",
      last_name: "Work",
      employee_number: "WL1",
      email: "amira-work@example.com",
      hire_date: "2025-01-01",
    },
  });
  expect(person.status(), await person.text()).toBe(201);
  const employee = (await person.json()).id;
  const member = (await (await api.get(`${API}/users`)).json()).users.find(
    (u: { is_you: boolean }) => u.is_you,
  );
  expect(
    (
      await api.put(`${API}/users/${member.id}/employee`, {
        headers,
        data: { employee_id: employee },
      })
    ).status(),
  ).toBe(200);
  const responsibility = await api.post(`${API}/employees/${employee}/responsibilities`, {
    headers,
    data: { text: "Coordinate handovers", sort: 0 },
  });
  expect(responsibility.status(), await responsibility.text()).toBe(201);
  const initial = new Date().toISOString().slice(0, 10);
  const day = (await (await api.get(`${API}/work-log/own?start=${initial}&end=${initial}`)).json())
    .today as string;
  const yesterday = new Date(Date.parse(`${day}T12:00:00Z`) - 86_400_000)
    .toISOString()
    .slice(0, 10);
  await page.goto("/my-work-log");
  await page.getByRole("button", { name: "Add entry", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add work log", exact: true });
  await add.getByLabel("Work date", { exact: true }).fill(day);
  await add.getByLabel("From", { exact: true }).fill("09:00");
  await add.getByLabel("To", { exact: true }).fill("12:00");
  await add
    .getByLabel("Responsibility", { exact: true })
    .selectOption((await responsibility.json()).id);
  await add.getByLabel("What I did", { exact: true }).fill("Finished reception checks");
  await add.getByRole("button", { name: "Save entry", exact: true }).click();
  await expect(add).toBeHidden();
  await page.getByRole("button", { name: "Edit entry", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "Edit work log", exact: true });
  await expect(edit.getByLabel("Work date", { exact: true })).toBeDisabled();
  await edit.getByLabel("To", { exact: true }).fill("13:00");
  await edit.getByRole("button", { name: "Save entry", exact: true }).click();
  await expect(edit).toBeHidden();
  await page.goto("/work-log");
  await page.getByLabel("From date", { exact: true }).fill(day);
  await page.getByLabel("To date", { exact: true }).fill(day);
  await page.getByLabel("Employee", { exact: true }).selectOption(employee);
  await page.getByLabel("Search work log", { exact: true }).fill("reception");
  await page.getByRole("button", { name: "Correct entry", exact: true }).click();
  const correct = page.getByRole("dialog", { name: "Correct work log", exact: true });
  await correct.getByLabel("To", { exact: true }).fill("14:00");
  await correct.getByLabel("What I did", { exact: true }).fill("Reviewed reception checks");
  await correct
    .getByLabel("Reason for correction", { exact: true })
    .fill("Employee confirmed the finishing time");
  await correct.getByRole("button", { name: "Save correction", exact: true }).click();
  await expect(correct).toBeHidden();
  const table = page.getByRole("grid", { name: "Work log entries", exact: true });
  await table.getByText("Reviewed reception checks", { exact: true }).click();
  const view = page.getByRole("dialog", { name: "Work log entry", exact: true });
  await expect(
    view
      .getByRole("region", { name: "Original work log entry", exact: true })
      .getByText("Finished reception checks", { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Remove entry", exact: true }).click();
  const remove = page.getByRole("dialog", { name: "Remove work log entry", exact: true });
  await remove
    .getByLabel("Reason for removal", { exact: true })
    .fill("Duplicate record reviewed with employee");
  await remove.getByRole("button", { name: "Remove entry", exact: true }).click();
  await expect(remove).toBeHidden();
  await page.getByRole("checkbox", { name: "Show removed", exact: true }).click();
  await expect(table.getByText("Removed", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "Show archived", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Admin work log mobile");
  const old = await api.post(`${API}/work-log/own`, {
    headers,
    data: {
      date: yesterday,
      from_time: "10:00",
      to_time: "11:00",
      responsibility_text: "Reception",
      description: "Yesterday's reception checks",
    },
  });
  expect(old.status(), await old.text()).toBe(201);
  expect((await old.json()).can_edit).toBe(false);
  await page.goto("/my-work-log");
  await page.getByLabel("From date", { exact: true }).fill(yesterday);
  await page.getByLabel("To date", { exact: true }).fill(day);
  await expect(page.getByRole("button", { name: "Edit entry", exact: true })).toHaveCount(0);
  await expect(page.getByText("Yesterday's reception checks", { exact: true })).toBeVisible();
  await audit(page, "My work log mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
