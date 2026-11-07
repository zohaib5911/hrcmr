/** T11.6 public careers: a visitor sees an open external posting and applies; a closed one is not found. */
import { API, csrfHeaders } from "../support/accounts";
import { expect, test } from "../support/fixtures";

import { BASE_URL } from "./helpers";

test("a visitor applies to an open posting, and a closed posting is not found", async ({
  context,
  browser,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const stamp = Date.now();
  const title = `Line cook ${stamp}`;
  const requisition = await api.post(`${API}/requisitions`, {
    headers,
    data: { job_title: title, headcount: 1 },
  });
  expect(requisition.status(), await requisition.text()).toBe(201);
  const requisitionId = (await requisition.json()).id;
  expect(
    (
      await api.patch(`${API}/requisitions/${requisitionId}/status`, {
        headers,
        data: { status: "open" },
      })
    ).status(),
  ).toBe(200);

  const open = await api.post(`${API}/postings`, {
    headers,
    data: { requisition_id: requisitionId, title, visibility: "external", vacancies: 1 },
  });
  expect(open.status(), await open.text()).toBe(201);
  const openId = (await open.json()).id;
  const opened = await api.patch(`${API}/postings/${openId}/status`, {
    headers,
    data: { status: "open" },
  });
  expect(opened.status(), await opened.text()).toBe(200);
  const link = new URL((await opened.json()).public_link);
  const [, careers, company, slug] = link.pathname.split("/");
  expect(careers).toBe("careers");

  const closedTitle = `Closed role ${stamp}`;
  const closed = await api.post(`${API}/postings`, {
    headers,
    data: {
      requisition_id: requisitionId,
      title: closedTitle,
      visibility: "external",
      vacancies: 1,
    },
  });
  expect(closed.status(), await closed.text()).toBe(201);
  const closedSlug = (await closed.json()).slug;

  const visitor = await browser.newContext({ baseURL: BASE_URL });
  try {
    const page = await visitor.newPage();
    await page.goto(`/careers/${company}`);
    await expect(page.getByRole("link", { name: new RegExp(title) })).toBeVisible();
    await page.getByRole("link", { name: new RegExp(title) }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await page.getByLabel("First name", { exact: true }).fill("Ivy");
    await page.getByLabel("Last name", { exact: true }).fill("Stone");
    await page.getByLabel("Email", { exact: true }).fill(`ivy-${stamp}@example.com`);
    await page.getByRole("checkbox", { name: /I agree that you may store my details/ }).check();
    await page.getByRole("button", { name: "Send application", exact: true }).click();
    await expect(page.getByText("Thank you for applying", { exact: true })).toBeVisible();

    const gone = await page.goto(`/careers/${company}/${closedSlug}`);
    expect(gone?.status()).toBe(404);
    const goneList = await page.goto(`/careers/${company}/${slug}-missing`);
    expect(goneList?.status()).toBe(404);
  } finally {
    await visitor.close();
  }
});
