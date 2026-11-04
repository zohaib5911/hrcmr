/** T10.2: the real worker generates fresh private Excel reports for the production UI. */
import { API, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("request worker-generated reports, download fresh files and keep recent jobs after reload", async ({
  page,
  context,
}) => {
  const headers = await csrfHeaders(context.request);
  const person = await context.request.post(`${API}/employees`, {
    headers,
    data: {
      first_name: "Jamie",
      last_name: "Report",
      employee_number: "REP-001",
      email: "report@example.com",
      hire_date: "2025-01-01",
    },
  });
  expect(person.status(), await person.text()).toBe(201);
  await page.goto("/reports");
  await expect(
    page.getByRole("heading", { name: "No reports requested", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Available reports", exact: true }).getByRole("button"),
  ).toHaveCount(7);
  await page.getByRole("button", { name: "Generate Employee Directory", exact: true }).click();
  const files = page.getByRole("region", { name: "Your report files", exact: true });
  await expect(files.getByText("Ready", { exact: true })).toBeVisible({ timeout: 20_000 });
  const requestJob = (await (await context.request.get(`${API}/reports/jobs`)).json())[0];
  expect(requestJob.status).toBe("ready");
  const download = page.waitForEvent("download");
  await files.getByRole("button", { name: /^Download Employee Directory requested / }).click();
  expect((await download).suggestedFilename()).toMatch(/^employee_directory-.*\.xlsx$/);
  const status = await context.request.get(`${API}/reports/jobs/${requestJob.id}`);
  expect(status.status(), await status.text()).toBe(200);
  expect((await status.json()).expires_in).toBe(60);
  // A second request must produce a fresh durable job rather than reuse the previous file.
  await page.getByRole("button", { name: "Generate Employee Directory", exact: true }).click();
  await expect(files.getByText("Ready", { exact: true })).toHaveCount(2, { timeout: 20_000 });
  const jobs = await (await context.request.get(`${API}/reports/jobs`)).json();
  expect(jobs).toHaveLength(2);
  expect(jobs[0].id).not.toBe(jobs[1].id);
  await page.reload();
  await expect(files.getByText("Ready", { exact: true })).toHaveCount(2);
  await page.setViewportSize({ width: 390, height: 900 });
  await page.getByRole("button", { name: "Generate Company Report", exact: true }).click();
  await expect(files.getByText("Ready", { exact: true })).toHaveCount(3, { timeout: 20_000 });
  await audit(page, "mobile reports and worker files");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
