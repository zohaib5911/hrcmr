/** T9.4 prerequisites, overnight shift, scoped rules and archived settings. */
import { API, csrfHeaders } from "../../support/accounts";
import { audit } from "../../support/axe";
import { expect, test } from "../../support/fixtures";

test("configure overnight shifts, late policy and regular days off", async ({ page, context }) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  await page.goto("/rota");
  await page.getByRole("link", { name: "Shift types and settings", exact: true }).click();
  await page.getByRole("radio", { name: "Late policy", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Set up a department, designation and shift first",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Departments", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Designations", exact: true })).toBeVisible();
  const department = await api.post(`${API}/departments`, { headers, data: { name: "Care" } });
  expect(department.status(), await department.text()).toBe(201);
  const deptId = (await department.json()).id;
  const designation = await api.post(`${API}/designations`, {
    headers,
    data: { department_id: deptId, title: "Carer" },
  });
  expect(designation.status(), await designation.text()).toBe(201);
  const jobId = (await designation.json()).id;
  await page.reload();
  await page.getByRole("button", { name: "Add shift type", exact: true }).click();
  const shift = page.getByRole("dialog", { name: "Add shift type", exact: true });
  await shift.getByRole("button", { name: "Night", exact: true }).click();
  await shift.getByLabel("Starts", { exact: true }).fill("22:00");
  await shift.getByLabel("Finishes", { exact: true }).fill("06:00");
  await shift.getByLabel("Break starts (optional)", { exact: true }).fill("02:00");
  await shift.getByLabel("Break finishes (optional)", { exact: true }).fill("02:30");
  await shift.getByLabel("Break finishes (optional)", { exact: true }).press("Tab");
  await expect(shift.getByRole("status")).toHaveText(/7.50 hours paid/);
  await shift.getByRole("button", { name: "Save shift type", exact: true }).click();
  await expect(shift).toBeHidden();
  await page.getByRole("radio", { name: "Late policy", exact: true }).click();
  await page.getByRole("button", { name: "Add late policy", exact: true }).click();
  const policy = page.getByRole("dialog", { name: "Add late policy", exact: true });
  await policy.getByLabel("Department", { exact: true }).selectOption(deptId);
  await policy.getByLabel("Designation", { exact: true }).selectOption(jobId);
  await policy.getByLabel("Shift type", { exact: true }).selectOption({ label: "Night" });
  await policy.getByLabel("Grace minutes", { exact: true }).fill("10");
  await policy.getByLabel("Allowed late days per month", { exact: true }).fill("2");
  await policy.getByLabel("Deduction type", { exact: true }).selectOption("percentage_of_day");
  await policy.getByLabel("Deduction percentage", { exact: true }).fill("5");
  await policy.getByRole("button", { name: "Save late policy", exact: true }).click();
  await expect(policy).toBeHidden();
  await page.getByRole("radio", { name: "Day off patterns", exact: true }).click();
  await page.getByRole("button", { name: "Add day off pattern", exact: true }).click();
  const off = page.getByRole("dialog", { name: "Add day off pattern", exact: true });
  await off.getByLabel("Department", { exact: true }).selectOption(deptId);
  await off.getByLabel("Designation", { exact: true }).selectOption(jobId);
  await off.getByLabel("Shift type", { exact: true }).selectOption({ label: "Night" });
  await off.getByRole("checkbox", { name: "Saturday", exact: true }).click();
  await off.getByRole("switch", { name: "Works public holidays", exact: true }).click();
  await off.getByRole("button", { name: "Save day off pattern", exact: true }).click();
  await expect(off).toBeHidden();
  await page.setViewportSize({ width: 390, height: 900 });
  await expect(page.getByText("Sunday · Works public holidays", { exact: true })).toBeVisible();
  await audit(page, "Day off settings mobile");
  await page.getByRole("button", { name: "Edit Care · Carer · Night", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "Edit day off pattern", exact: true });
  await expect(edit.getByRole("checkbox", { name: "Sunday", exact: true })).toBeChecked();
  await edit.getByRole("checkbox", { name: "Monday", exact: true }).click();
  await edit.getByRole("button", { name: "Save day off pattern", exact: true }).click();
  await expect(edit).toBeHidden();
  await page.getByRole("radio", { name: "Shift types", exact: true }).click();
  await page.getByRole("button", { name: "Archive Night", exact: true }).click();
  await page.getByRole("button", { name: "Archive setting", exact: true }).click();
  await expect(
    page.getByText("Archive this shift's late policies and day off patterns first.", {
      exact: true,
    }),
  ).toBeVisible();
  for (const label of ["Late policy", "Day off patterns"]) {
    await page.getByRole("radio", { name: label, exact: true }).click();
    await page.getByRole("button", { name: "Archive Care · Carer · Night", exact: true }).click();
    await page.getByRole("button", { name: "Archive setting", exact: true }).click();
    await expect
      .poll(
        async () =>
          (
            await (
              await api.get(
                `${API}/rota/${label === "Late policy" ? "late-policies" : "day-off-patterns"}`,
              )
            ).json()
          ).length,
      )
      .toBe(0);
  }
  await page.getByRole("radio", { name: "Shift types", exact: true }).click();
  await audit(page, "Shift settings mobile");
  await page.getByRole("button", { name: "Archive Night", exact: true }).click();
  await page.getByRole("button", { name: "Archive setting", exact: true }).click();
  await expect
    .poll(async () => (await (await api.get(`${API}/rota/shift-types`)).json()).length)
    .toBe(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
