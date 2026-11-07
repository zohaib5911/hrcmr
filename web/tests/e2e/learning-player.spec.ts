/** T13.1 course player: progress survives a reload, and a check below the pass mark does not complete. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("a learner moves through a course, a reload keeps their place, and only a passing check completes it", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const stamp = Date.now().toString(36);
  const made = await api.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Lena",
      last_name: `Learner${stamp}`,
      employee_number: `LN${stamp}`,
      email: `ln-${stamp}@example.com`,
      hire_date: "2025-01-01",
    },
  });
  expect(made.status(), await made.text()).toBe(201);
  const employee = (await made.json()).id;
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
  const catalogue = await (await api.get(`${API}/learning/courses`)).json();
  const course = catalogue.find((c: { slug: string }) => c.slug === "e2e-test-course");
  expect(course, "the test course is loaded by the e2e server").toBeTruthy();
  const assigned = await api.post(`${API}/learning/assignments`, {
    headers,
    data: { course_ids: [course.id], employee_ids: [employee], due_on: "2026-12-01" },
  });
  expect(assigned.status(), await assigned.text()).toBe(201);
  const own = await (await api.get(`${API}/learning/assignments/own`)).json();
  expect(own).toHaveLength(1);

  await page.goto(`/learning/assignments/${own[0].id}`);
  await expect(
    page.getByRole("heading", { name: course.title, level: 1, exact: true }),
  ).toBeVisible();
  // The answers are not sent to the page until the check is submitted.
  await expect(page.getByText("Option C", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "2. Second section", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "2. Second section", exact: true }),
  ).toHaveAttribute("aria-current", "step");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "2. Second section", exact: true }),
  ).toHaveAttribute("aria-current", "step");

  await page.getByRole("button", { name: "Check (2 questions)", exact: false }).click();
  const first = page.getByRole("group", { name: /first question/ });
  const second = page.getByRole("group", { name: /second question/ });
  await first.getByLabel("Option A", { exact: true }).check();
  await second.getByLabel("Option A", { exact: true }).check();
  await page.getByRole("button", { name: "Submit the check", exact: true }).click();
  await expect(page.getByText("You scored 0%.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Complete the course", exact: true })).toHaveCount(
    0,
  );

  await page.getByRole("button", { name: "Try the check again", exact: true }).click();
  await first.getByLabel("Option C", { exact: true }).check();
  await second.getByLabel("Option A", { exact: true }).check();
  await page.getByRole("button", { name: "Submit the check", exact: true }).click();
  await expect(page.getByText("You scored 50%.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Complete the course", exact: true })).toHaveCount(
    0,
  );

  await page.getByRole("button", { name: "Try the check again", exact: true }).click();
  await first.getByLabel("Option C", { exact: true }).check();
  await second.getByLabel("Option B", { exact: true }).check();
  await page.getByRole("button", { name: "Submit the check", exact: true }).click();
  await expect(page.getByText("You scored 100%.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Complete the course", exact: true }).click();
  await expect(page.getByText("Completed", { exact: false }).first()).toBeVisible();

  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Learning player mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
