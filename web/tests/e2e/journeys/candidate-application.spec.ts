/** T11.1 requisitions: create, approve through the sheet, and cancel after a confirmation. */
import { API, csrfHeaders } from "../../support/accounts";
import { expect, test } from "../../support/fixtures";

test("apply a candidate to an open posting, move them forward, and see the pipeline count", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const stamp = Date.now();
  const requisition = await api.post(`${API}/requisitions`, {
    headers,
    data: { job_title: `Barista ${stamp}`, headcount: 1 },
  });
  expect(requisition.status(), await requisition.text()).toBe(201);
  const requisitionId = (await requisition.json()).id;
  const opened = await api.patch(`${API}/requisitions/${requisitionId}/status`, {
    headers,
    data: { status: "open" },
  });
  expect(opened.status(), await opened.text()).toBe(200);
  const posting = await api.post(`${API}/postings`, {
    headers,
    data: {
      requisition_id: requisitionId,
      title: `Barista ${stamp}`,
      visibility: "external",
      vacancies: 1,
    },
  });
  expect(posting.status(), await posting.text()).toBe(201);
  const postingId = (await posting.json()).id;
  expect(
    (
      await api.patch(`${API}/postings/${postingId}/status`, { headers, data: { status: "open" } })
    ).status(),
  ).toBe(200);
  const candidate = await api.post(`${API}/candidates`, {
    headers,
    data: { first_name: "Noor", last_name: `Pipeline${stamp}` },
  });
  expect(candidate.status(), await candidate.text()).toBe(201);
  const candidateId = (await candidate.json()).id;

  await page.goto(`/recruitment/candidates/${candidateId}`);
  await page.getByRole("tab", { name: "Applications", exact: true }).click();
  await page.getByLabel("Apply to posting", { exact: true }).selectOption(postingId);
  await page.getByRole("button", { name: "Add application", exact: true }).click();
  const link = page.getByRole("link", { name: new RegExp(`Barista ${stamp}`) });
  await expect(link.getByText("Job Applied", { exact: true })).toBeVisible();
  await link.click();

  await expect(page).toHaveURL(/\/recruitment\/applications\//);
  await page.getByRole("button", { name: "Move to Shortlisted", exact: true }).click();
  await expect(
    page.getByText("Waiting for an interview to be arranged.", { exact: true }),
  ).toBeVisible();

  await page.goto("/recruitment");
  await page.getByRole("tab", { name: /^Applications/ }).click();
  const button = page.getByRole("button", { name: /^Shortlisted \(/ });
  await expect
    .poll(async () => Number(/\((\d+)\)/.exec(await button.innerText())?.[1] ?? "0"))
    .toBeGreaterThanOrEqual(1);
});
