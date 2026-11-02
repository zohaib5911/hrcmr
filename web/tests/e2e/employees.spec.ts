/**
 * The employee list (plan T6.1), against the real API and a real signed-in Company Admin. There is no
 * way to add an employee until T6.2, so this checks the empty company: the summary line, the pills,
 * the filters, the archived list and the accessibility check. Rows, filters and what each role may
 * see are covered by the API tests and lib/employees/list.test.ts.
 */
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

async function open(
  page: import("@playwright/test").Page,
  path = "/employees",
  heading = "Employees",
) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("an empty company shows the summary, the pills and an empty state", async ({ page }) => {
  await open(page);
  await expect(page.getByText("0 employees", { exact: true })).toBeVisible();
  const pills = page.getByRole("radiogroup", { name: "Show" });
  await expect(pills.getByRole("radio", { name: "All" })).toBeChecked();
  for (const label of ["Active", "On leave", "Leavers"]) {
    await expect(pills.getByRole("radio", { name: label })).toBeVisible();
  }
  await expect(page.getByText("No employees yet")).toBeVisible();
  await pills.getByRole("radio", { name: "On leave" }).click();
  await expect(page.getByText("Nobody matches")).toBeVisible();
});

test("a deep link chooses the pill, and the archived list is one toggle away", async ({ page }) => {
  await open(page, "/employees?status=leaver");
  await expect(
    page.getByRole("radiogroup", { name: "Show" }).getByRole("radio", { name: "Leavers" }),
  ).toBeChecked();
  await page.getByRole("switch", { name: "Show archived" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Archived employees" })).toBeVisible();
  await expect(page.getByText("No archived employees")).toBeVisible();
  await page.getByRole("switch", { name: "Show archived" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Employees" })).toBeVisible();
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of [390, 1280] as const) {
      test(`the list at ${width} px has no sideways scroll and passes axe`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await audit(page, `${colorScheme} employees ${width}px`);
      });
    }
  });
}
