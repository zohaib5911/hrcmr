/** T12.2 org chart: search finds a person and opens their card, the list shows the same people, and the PDF downloads. */
import { API, csrfHeaders } from "../../support/accounts";
import { audit } from "../../support/axe";
import { expect, test } from "../../support/fixtures";

test("search finds a person on the chart, opens their card, and the list and PDF agree", async ({
  page,
  context,
}) => {
  const api = context.request;
  const headers = await csrfHeaders(api);
  const stamp = Date.now().toString(36);
  const hire = async (first: string, last: string, number: string) => {
    const created = await api.post(`${API}/employees`, {
      headers,
      data: {
        first_name: first,
        last_name: last,
        employee_number: number,
        email: `${number.toLowerCase()}@example.com`,
        hire_date: "2025-01-01",
      },
    });
    expect(created.status(), await created.text()).toBe(201);
    return (await created.json()).id as string;
  };
  const boss = await hire("Olive", `Top${stamp}`, `OT${stamp}`);
  const report = await hire("Sam", `Under${stamp}`, `SU${stamp}`);
  const reporting = await api.post(`${API}/employees/${report}/assignments`, {
    headers,
    data: {
      employment_type: "full_time",
      effective_from: "2025-01-01",
      reporting_authority_employee_id: boss,
    },
  });
  expect(reporting.status(), await reporting.text()).toBe(201);

  await page.goto("/organogram");
  await expect(
    page.getByRole("heading", { name: "Org chart", level: 1, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Unassigned", level: 2, exact: true }),
  ).toBeVisible();

  const search = page.getByLabel("Search people", { exact: true });
  await search.fill(`Under${stamp}`);
  const matches = page.getByRole("list", { name: "Matching people", exact: true });
  await matches.getByRole("button", { name: `Sam Under${stamp}` }).click();
  const card = page.getByRole("dialog", { name: `Sam Under${stamp}`, exact: true });
  await expect(card).toBeVisible();
  await expect(
    card.getByRole("link", { name: "Open employee record", exact: true }),
  ).toHaveAttribute("href", `/employees/${report}`);
  await page.keyboard.press("Escape");
  await expect(card).toBeHidden();

  await page.getByRole("radio", { name: "List", exact: true }).click();
  const table = page.getByRole("grid", { name: "People in the org chart", exact: true });
  await expect(table.getByText(`Sam Under${stamp}`, { exact: true })).toBeVisible();
  await table.getByRole("button", { name: `Open Sam Under${stamp}`, exact: true }).click();
  await expect(page.getByRole("dialog", { name: `Sam Under${stamp}`, exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("radio", { name: "Chart", exact: true }).click();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("org-chart.pdf");

  await page.setViewportSize({ width: 390, height: 900 });
  await audit(page, "Org chart mobile");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
