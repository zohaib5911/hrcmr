/** Phase 12 gate: the org chart and its list view at 390/1280 px in light/dark. */
import path from "node:path";
import { type Page, request } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-12");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");
// Independent companies keep the visual states identical instead of accumulating seed data.
test.use({
  storageState: async ({}, use) => {
    const api = await request.newContext();
    try {
      await createSignedInAdmin(api);
      // eslint-disable-next-line react-hooks/rules-of-hooks -- Playwright fixture callback.
      await use(await api.storageState());
    } finally {
      await api.dispose();
    }
  },
});

async function shoot(page: Page, name: string, modal = false) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  await audit(page, name, { modal });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: !modal,
    animations: "disabled",
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`Org chart at ${width}px`, async ({ page, context }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const api = context.request;
        const headers = await csrfHeaders(api);
        const hire = async (first: string, last: string, number: string) => {
          const made = await api.post(`${API}/employees`, {
            headers,
            data: {
              first_name: first,
              last_name: last,
              employee_number: number,
              email: `${number.toLowerCase()}@example.com`,
              hire_date: "2025-01-01",
            },
          });
          expect(made.status(), await made.text()).toBe(201);
          return (await made.json()).id as string;
        };
        const assign = async (person: string, manager: string | null) => {
          const made = await api.post(`${API}/employees/${person}/assignments`, {
            headers,
            data: {
              employment_type: "full_time",
              effective_from: "2025-01-01",
              reporting_authority_employee_id: manager,
            },
          });
          expect(made.status(), await made.text()).toBe(201);
        };
        const head = await hire("Ada", "Morrow", `HEAD${suffix.replace(/\W/g, "")}`);
        await assign(head, null);
        for (const { first, last } of [
          { first: "Ben", last: "Okafor" },
          { first: "Clara", last: "Ruiz" },
        ]) {
          const lead = await hire(first, last, `LEAD${first}${suffix.replace(/\W/g, "")}`);
          await assign(lead, head);
          for (const member of ["Dev", "Eve", "Finn"]) {
            const person = await hire(
              member,
              `${last}${suffix.replace(/\W/g, "")}`,
              `TEAM${member}${first}${suffix.replace(/\W/g, "")}`,
            );
            await assign(person, lead);
          }
        }
        await page.goto("/organogram");
        await expect(
          page.getByRole("heading", { name: "Org chart", level: 1, exact: true }),
        ).toBeVisible();
        await expect(page.getByRole("button", { name: /Ada Morrow/ })).toBeVisible();
        await shoot(page, `org-chart-${suffix}`);
        await page.getByRole("radio", { name: "List", exact: true }).click();
        // A table on wide screens; the same people as a labelled list on phones.
        await expect(
          page
            .getByRole("grid", { name: "People in the org chart", exact: true })
            .or(page.getByRole("list", { name: "People in the org chart", exact: true })),
        ).toBeVisible();
        await shoot(page, `org-list-${suffix}`);
      });
    }
  });
}
