/** Phase 13 gate: learning report, my learning, a completed course and the public check, at 390/1280 px in light and dark. */
import path from "node:path";
import { type Page, request } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-13");
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
      test(`Learning at ${width}px`, async ({ page, context }) => {
        test.setTimeout(240_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const api = context.request;
        const headers = await csrfHeaders(api);
        const stamp = `${suffix.replace(/\W/g, "")}${Date.now().toString(36)}`;
        const made = await api.post(`${API}/employees`, {
          headers,
          data: {
            first_name: "Nadia",
            last_name: `Shot${stamp}`,
            employee_number: `NS${stamp}`.slice(0, 40),
            email: `ns-${stamp}@example.com`.slice(0, 60),
            hire_date: "2025-01-01",
          },
        });
        expect(made.status(), await made.text()).toBe(201);
        const employee = (await made.json()).id;
        const me = (await (await api.get(`${API}/users`)).json()).users.find(
          (u: { is_you: boolean }) => u.is_you,
        );
        expect(
          (
            await api.put(`${API}/users/${me.id}/employee`, {
              headers,
              data: { employee_id: employee },
            })
          ).status(),
        ).toBe(200);
        const course = (await (await api.get(`${API}/learning/courses`)).json()).find(
          (c: { slug: string }) => c.slug === "e2e-test-course",
        );
        expect(course, "the test course is loaded by the e2e server").toBeTruthy();
        const assigned = await api.post(`${API}/learning/assignments`, {
          headers,
          data: {
            course_ids: [course.id],
            scope: "named",
            employee_ids: [employee],
            due_on: "2026-12-01",
          },
        });
        expect(assigned.status(), await assigned.text()).toBe(201);
        const assignment = (await (await api.get(`${API}/learning/assignments/own`)).json())[0].id;
        const base = `${API}/learning/assignments/${assignment}`;
        expect(
          (await api.post(`${base}/quiz`, { headers, data: { answers: [2, 1] } })).status(),
        ).toBe(200);
        expect((await api.post(`${base}/complete`, { headers })).status()).toBe(200);
        const reference = (await (await api.get(`${base}/certificate`)).json()).reference;

        await page.goto("/learning");
        await expect(
          page.getByRole("heading", { name: "Learning", level: 1, exact: true }),
        ).toBeVisible();
        await shoot(page, `learning-report-${suffix}`);

        await page.goto("/learning/my");
        await expect(
          page.getByRole("heading", { name: "My learning", level: 1, exact: true }),
        ).toBeVisible();
        await shoot(page, `my-learning-${suffix}`);

        await page.goto(`/learning/assignments/${assignment}`);
        await expect(
          page.getByRole("button", { name: "Download certificate", exact: true }),
        ).toBeVisible();
        await shoot(page, `course-completed-${suffix}`);

        await page.goto(`/verify?ref=${reference}`);
        await expect(
          page.getByRole("heading", { name: "Check a certificate", level: 1, exact: true }),
        ).toBeVisible();
        await page.getByRole("button", { name: "Check certificate", exact: true }).click();
        await expect(page.getByLabel("Certificate details")).toBeVisible();
        await shoot(page, `verify-certificate-${suffix}`);
      });
    }
  });
}
