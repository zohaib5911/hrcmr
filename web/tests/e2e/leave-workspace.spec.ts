/** T8.4 real API workflow: own/on-behalf requests, decisions and reasoned balances. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("leave request, approval, calendar, profile adjustments and own cancellation", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const pattern = await api.put(`${API}/working-pattern`, {
    headers,
    data: {
      days: Array.from({ length: 7 }, (_, i) => ({
        weekday: i + 1,
        is_working: i < 5,
        hours: i < 5 ? "8" : "0",
      })),
      bank_holidays_non_working: true,
    },
  });
  expect(pattern.status(), await pattern.text()).toBe(200);
  const people: string[] = [];
  for (const [i, name] of ["Amina", "Ben"].entries()) {
    const person = await api.post(`${API}/employees`, {
      headers,
      data: {
        first_name: name,
        last_name: "Leave",
        email: `${name.toLowerCase()}@example.com`,
        employee_number: `L${i}`,
        hire_date: "2025-01-01",
      },
    });
    expect(person.status(), await person.text()).toBe(201);
    people.push((await person.json()).id);
  }
  const users = await api.get(`${API}/users`);
  expect(users.status(), await users.text()).toBe(200);
  const membership = (await users.json()).users.find((u: { is_you: boolean }) => u.is_you);
  const link = await api.put(`${API}/users/${membership.id}/employee`, {
    headers,
    data: { employee_id: people[0] },
  });
  expect(link.status(), await link.text()).toBe(200);

  await page.goto("/leave");
  await expect(page.getByRole("heading", { level: 1, name: "Leave", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Request on behalf" }).click();
  const form = page.getByRole("dialog", { name: "Request leave on behalf" });
  await form.getByLabel("Employee", { exact: true }).selectOption(people[1]!);
  await form.getByLabel("Leave type", { exact: true }).selectOption({ label: "Annual Leave" });
  await form.getByLabel("Start date", { exact: true }).fill("2026-11-09");
  await form.getByLabel("End date", { exact: true }).fill("2026-11-10");
  await expect(form.getByRole("status")).toHaveText("2 working days");
  await form.getByRole("button", { name: "Submit request" }).click();
  await expect(form).toBeHidden();
  await expect(
    page.getByRole("grid", { name: "Leave requests" }).getByText("pending", { exact: true }),
  ).toBeVisible();
  await page.goto("/my-approvals");
  await page.getByRole("button", { name: "Review request", exact: true }).click();
  const review = page.getByRole("dialog", { name: "Review leave request" });
  await review.getByLabel("Decision note (optional)").fill("Coverage checked");
  await expect(review.getByRole("button", { name: "Approve", exact: true })).toBeEnabled();
  await review.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(review).toBeHidden();
  await expect(page.getByText("No requests awaiting your decision")).toBeVisible();
  await page.goto("/leave");
  await page.getByLabel("Month", { exact: true }).fill("2026-11");
  await expect(
    page.getByRole("button", { name: "Monday 9 November 2026, 1 leave requests" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Monday 9 November 2026, 1 leave requests" }).click();
  await expect(
    page.getByText("Ben Leave · Annual Leave · approved", { exact: true }),
  ).toBeVisible();

  await page.goto(`/employees/${people[1]}?tab=leave`);
  await expect(
    page.getByRole("button", { name: "Adjust Annual Leave", exact: true }),
  ).toBeVisible();
  for (const [operation, amount] of [
    ["grant", "2"],
    ["deduct", "1"],
    ["set", "15"],
  ]) {
    await page.getByRole("button", { name: "Adjust Annual Leave", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Adjust Annual Leave", exact: true });
    await sheet.getByLabel("Action", { exact: true }).selectOption(operation!);
    await sheet
      .getByLabel(operation === "set" ? "New balance (days)" : "Days", { exact: true })
      .fill(amount!);
    await sheet.getByLabel("Reason", { exact: true }).fill("Reviewed by HR");
    await sheet.getByRole("button", { name: "Save balance" }).click();
    await expect(sheet).toBeHidden();
  }
  const balance = page.getByRole("region", { name: "Leave balances", exact: true });
  await expect(balance.getByRole("gridcell", { name: "15", exact: true })).toBeVisible();

  await page.goto("/my-leave");
  await page.getByRole("button", { name: "Request leave", exact: true }).click();
  const own = page.getByRole("dialog", { name: "Request leave", exact: true });
  await own.getByLabel("Start date", { exact: true }).fill("2026-11-12");
  await own.getByLabel("End date", { exact: true }).fill("2026-11-12");
  await expect(own.getByRole("status")).toHaveText("1 working days");
  await own.getByRole("button", { name: "Submit request" }).click();
  await expect(own).toBeHidden();
  await page.getByRole("button", { name: "Cancel request", exact: true }).click();
  await expect(
    page.getByRole("grid", { name: "Leave requests" }).getByText("cancelled", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "My leave mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
