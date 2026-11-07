/** Phase 10 gate: documents, reports, policies (list, detail, wizard) and My Documents at 390/1280 px in light/dark. */
import { mkdirSync } from "node:fs";
import path from "node:path";
import { request, type Page } from "@playwright/test";
import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-10");
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

const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n" +
    "2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n",
);

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
      test(`Documents, reports and policies at ${width}px`, async ({ page, context }) => {
        test.setTimeout(300_000);
        mkdirSync(OUT, { recursive: true });
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const api = context.request;
        const headers = await csrfHeaders(api);
        const employee = await api.post(`${API}/employees`, {
          headers,
          data: {
            first_name: "Ruth",
            last_name: "Okafor",
            employee_number: `P10${width}`,
            email: `ruth-${suffix}@example.com`,
            hire_date: "2025-01-01",
          },
        });
        expect(employee.status(), await employee.text()).toBe(201);
        const created = await api.post(`${API}/policies`, {
          headers,
          data: {
            title: "Staff handbook 2026",
            category: "employee_handbook",
            confirmation_mode: "accept",
            audience_type: "everyone",
            accept_within_days: 14,
          },
        });
        expect(created.status(), await created.text()).toBe(201);
        const policy = (await created.json()).id as string;
        const uploaded = await api.post(`${API}/policies/${policy}/file`, {
          headers,
          multipart: { file: { name: "handbook.pdf", mimeType: "application/pdf", buffer: PDF } },
        });
        expect(uploaded.status(), await uploaded.text()).toBe(200);
        await expect
          .poll(
            async () =>
              (await (await api.get(`${API}/policies/${policy}`)).json()).scan_status as string,
            { timeout: 60_000 },
          )
          .toBe("clean");
        const preview = await (await api.get(`${API}/policies/${policy}/recipients`)).json();
        const sent = await api.post(`${API}/policies/${policy}/send`, {
          headers,
          data: { preview_token: preview.preview_token },
        });
        expect(sent.status(), await sent.text()).toBe(200);

        await page.goto("/documents");
        await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
        await shoot(page, `documents-${suffix}`);

        await page.goto("/reports");
        await expect(page.getByRole("heading", { name: "Reports", exact: true })).toBeVisible();
        await shoot(page, `reports-${suffix}`);

        await page.goto("/policies");
        await expect(page.getByRole("heading", { name: "Policies", exact: true })).toBeVisible();
        await expect(
          page.getByRole("link", { name: "Staff handbook 2026", exact: true }),
        ).toBeVisible();
        await shoot(page, `policies-list-${suffix}`);

        await page.goto(`/policies/${policy}`);
        await expect(
          page.getByRole("heading", { name: "Staff handbook 2026", exact: true }),
        ).toBeVisible();
        await shoot(page, `policy-detail-${suffix}`);

        await page.goto("/policies");
        await page.getByRole("button", { name: "New document", exact: true }).first().click();
        await expect(page.getByRole("dialog", { name: "New document", exact: true })).toBeVisible();
        await shoot(page, `policy-wizard-${suffix}`, true);
        await page.keyboard.press("Escape");

        await page.goto("/my-documents");
        await expect(
          page.getByRole("heading", { name: "My documents", exact: true }),
        ).toBeVisible();
        await shoot(page, `my-documents-${suffix}`);
      });
    }
  });
}
