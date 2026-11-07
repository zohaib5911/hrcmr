/** Phase 11 gate: recruitment (tabs, candidate, application) and the public careers pages at 390/1280 px. */
import { mkdirSync } from "node:fs";
import path from "node:path";
import { request, type Page } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

import { BASE_URL } from "./helpers";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-11");
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
      test(`Recruitment and careers at ${width}px`, async ({ page, context, browser }) => {
        test.setTimeout(300_000);
        mkdirSync(OUT, { recursive: true });
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const api = context.request;
        const headers = await csrfHeaders(api);
        const stamp = Date.now();
        const title = `Kitchen porter ${width}${colorScheme} ${stamp}`;
        const requisition = await api.post(`${API}/requisitions`, {
          headers,
          data: {
            job_title: title,
            headcount: 2,
            budget_from: "24000",
            budget_to: "26000",
            budget_per: "year",
          },
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
        const posting = await api.post(`${API}/postings`, {
          headers,
          data: {
            requisition_id: requisitionId,
            title,
            visibility: "external",
            vacancies: 2,
            description: "About the role",
          },
        });
        expect(posting.status(), await posting.text()).toBe(201);
        const postingId = (await posting.json()).id;
        const opened = await api.patch(`${API}/postings/${postingId}/status`, {
          headers,
          data: { status: "open" },
        });
        expect(opened.status(), await opened.text()).toBe(200);
        const link = new URL((await opened.json()).public_link);
        const [, , company, slug] = link.pathname.split("/");
        const candidate = await api.post(`${API}/candidates`, {
          headers,
          data: {
            first_name: "Priya",
            last_name: `Shah${width}`,
            email: `priya-${suffix}@example.com`,
            source: "Referral",
          },
        });
        expect(candidate.status(), await candidate.text()).toBe(201);
        const candidateId = (await candidate.json()).id;
        const application = await api.post(`${API}/applications`, {
          headers,
          data: { candidate_id: candidateId, posting_id: postingId },
        });
        expect(application.status(), await application.text()).toBe(201);
        const applicationId = (await application.json()).id;

        await page.goto("/recruitment");
        await expect(page.getByRole("heading", { name: "Recruitment", exact: true })).toBeVisible();
        await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
        await shoot(page, `recruitment-requisitions-${suffix}`);
        await page.getByRole("tab", { name: /^Postings/ }).click();
        await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
        await shoot(page, `recruitment-postings-${suffix}`);
        await page.getByRole("tab", { name: /^Candidates/ }).click();
        await expect(page.getByText(`Priya Shah${width}`, { exact: true })).toBeVisible();
        await shoot(page, `recruitment-candidates-${suffix}`);
        await page.getByRole("tab", { name: /^Applications/ }).click();
        await expect(page.getByRole("button", { name: /^Job Applied \(/ })).toBeVisible();
        await shoot(page, `recruitment-applications-${suffix}`);

        await page.goto(`/recruitment/candidates/${candidateId}`);
        await expect(
          page.getByRole("heading", { name: `Priya Shah${width}`, exact: true }),
        ).toBeVisible();
        await shoot(page, `candidate-profile-${suffix}`);

        await page.goto(`/recruitment/applications/${applicationId}`);
        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
        await shoot(page, `application-page-${suffix}`);

        const visitor = await browser.newContext({ baseURL: BASE_URL, colorScheme });
        try {
          const careers = await visitor.newPage();
          await careers.setViewportSize({ width, height: 900 });
          await careers.goto(`/careers/${company}`);
          await expect(careers.getByRole("link", { name: new RegExp(title) })).toBeVisible();
          await shoot(careers, `careers-list-${suffix}`);
          await careers.goto(`/careers/${company}/${slug}`);
          await expect(careers.getByRole("heading", { name: title, exact: true })).toBeVisible();
          await shoot(careers, `careers-posting-${suffix}`);
        } finally {
          await visitor.close();
        }
      });
    }
  });
}
