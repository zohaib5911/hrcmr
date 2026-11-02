/** Phase 6 gate evidence: 390/1280 px, light/dark. Run only with SCREENSHOTS=1. */
import path from "node:path";
import type { Page } from "@playwright/test";
import { API, csrfHeaders } from "../support/accounts";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-6");
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
      test("Employees at " + width + " px", async ({ page }) => {
        test.setTimeout(90_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = colorScheme + "-" + width;
        const headers = await csrfHeaders(page.request);
        const made = await page.request.post(API + "/employees", {
          headers,
          data: {
            first_name: "Mara",
            last_name: "Rosen",
            email: "mara@example.com",
            employee_number: "QA-" + suffix,
            hire_date: "2025-01-06",
            phone: "07700 900123",
          },
        });
        expect(made.status(), await made.text()).toBe(201);
        const { id } = (await made.json()) as { id: string };
        const base = API + "/employees/" + id;
        for (const [route, data] of [
          [
            "assignments",
            { employment_type: "full_time", hours_per_day: "7.5", effective_from: "2025-01-06" },
          ],
          ["responsibilities", { text: "Support customers and maintain accurate records" }],
          [
            "compensation",
            {
              amount: "42000",
              frequency: "annual",
              contracted_hours_per_week: "37.5",
              effective_from: "2025-01-06",
            },
          ],
          [
            "education",
            {
              qualification: "BSc",
              subject: "Business management",
              institution: "Example University",
              year: 2021,
            },
          ],
          ["contacts", { name: "Sam Rosen", relationship: "partner", phone: "07700 900456" }],
        ] as const) {
          const response = await page.request.post(base + "/" + route, { headers, data });
          expect(response.status(), await response.text()).toBe(201);
        }
        await page.goto("/employees");
        await expect(
          page.getByRole("heading", { level: 1, name: "Employees", exact: true }),
        ).toBeVisible();
        await shoot(page, "list-" + suffix);
        await page.goto("/employees/archived");
        await expect(
          page.getByRole("heading", { level: 1, name: "Archived employees" }),
        ).toBeVisible();
        await shoot(page, "archived-" + suffix);
        await page.goto("/employees/new");
        await expect(page.getByRole("heading", { level: 1, name: "New employee" })).toBeVisible();
        await shoot(page, "create-" + suffix);
        await page.goto("/employees/" + id);
        await expect(page.getByRole("heading", { level: 1, name: "Mara Rosen" })).toBeVisible();
        await expect(
          page
            .getByRole("region", { name: "Summary", exact: true })
            .getByText("full time", { exact: true }),
        ).toBeVisible();
        await shoot(page, "overview-" + suffix);
        for (const tab of [
          "Personal",
          "Employment",
          "Documents",
          "Leave",
          "Attendance",
          "Learning",
          "Activity",
        ]) {
          await page.getByRole("tab", { name: tab, exact: true }).click();
          await page.waitForLoadState("networkidle");
          if (tab === "Activity")
            await expect(page.getByText("employee · created", { exact: true })).toBeVisible();
          if (tab === "Documents") await expect(page.getByText("No documents yet.")).toBeVisible();
          await shoot(page, tab.toLowerCase() + "-" + suffix);
          if (tab === "Employment") {
            await page.getByRole("button", { name: "Show salary", exact: true }).click();
            await expect(
              page.getByText("£42,000.00 annual", { exact: true }).first(),
            ).toBeVisible();
            await shoot(page, "salary-" + suffix);
            await page.getByRole("button", { name: "Change role", exact: true }).click();
            await expect(page.getByRole("dialog")).toBeVisible();
            await shoot(page, "role-sheet-" + suffix);
            await page.keyboard.press("Escape");
          }
          if (tab === "Documents") {
            await page.getByRole("button", { name: "Upload document", exact: true }).click();
            await expect(page.getByRole("dialog")).toBeVisible();
            await shoot(page, "upload-sheet-" + suffix);
            await page.keyboard.press("Escape");
          }
        }
        await page.goto("/company/users");
        await page
          .getByRole("button", { name: "Link employee for Amira Hassan", exact: true })
          .click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await shoot(page, "employee-link-" + suffix);
      });
    }
  });
}
