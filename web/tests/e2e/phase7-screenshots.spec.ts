/** Phase 7 gate evidence: 390/1280 px, light/dark. */
import path from "node:path";
import type { Page } from "@playwright/test";
import { API, csrfHeaders } from "../support/accounts";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-7");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");

async function shoot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  await page.mouse.move(0, 0);
  await page.waitForTimeout(500);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  const dialogOpen = await page.getByRole("dialog").isVisible();
  await page.screenshot({ path: path.join(OUT, name + ".png"), fullPage: !dialogOpen });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test("Compliance at " + width + " px", async ({ page }) => {
        test.setTimeout(120_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = colorScheme + "-" + width;
        const headers = await csrfHeaders(page.request);
        const made = await page.request.post(API + "/employees", {
          headers,
          data: {
            first_name: "Mira",
            last_name: "Patel",
            email: "mira@example.com",
            employee_number: "COMP-" + suffix,
            hire_date: "2025-01-06",
          },
        });
        expect(made.status(), await made.text()).toBe(201);
        const { id } = (await made.json()) as { id: string };
        const doc = await page.request.post(API + "/employees/" + id + "/sponsor-documents", {
          headers,
          data: {
            doc_type: "visa",
            visa_route: "skilled_worker",
            expiry_date: new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10),
          },
        });
        expect(doc.status(), await doc.text()).toBe(201);
        for (const [route, heading, name] of [
          ["/sponsor-compliance", "Sponsor compliance", "hub"],
          ["/sponsor-compliance/migrant-employees", "Sponsored employees", "sponsored"],
          ["/sponsor-compliance/reminders", "Compliance reminders", "reminders"],
          ["/sponsor-compliance/change-of-circumstances", "Change of circumstances", "changes"],
          ["/sponsor-compliance/dossier", "Sponsor Management Dossier", "dossier"],
        ] as const) {
          await page.goto(route);
          await expect(
            page.getByRole("heading", { level: 1, name: heading, exact: true }),
          ).toBeVisible();
          await expect(page.getByRole("main").getByRole("status")).toHaveCount(0);
          await shoot(page, name + "-" + suffix);
        }
        await page.goto("/employees/" + id + "?tab=rtw");
        await expect(
          page.getByRole("region", { name: "Current Right to Work check" }),
        ).toBeVisible();
        await shoot(page, "rtw-" + suffix);
        await page.getByRole("button", { name: "Record a check", exact: true }).click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await shoot(page, "rtw-form-" + suffix);
        await page.getByRole("button", { name: "Cancel", exact: true }).click();
        await page.getByRole("tab", { name: "Sponsor compliance", exact: true }).click();
        await expect(
          page.getByRole("region", { name: "Visa document", exact: true }),
        ).toBeVisible();
        await shoot(page, "sponsor-record-" + suffix);
        await page.getByRole("button", { name: /^Notifications/ }).click();
        await expect(
          page.getByRole("dialog", { name: "Notifications", exact: true }),
        ).toBeVisible();
        await shoot(page, "bell-" + suffix);
      });
    }
  });
}
