/**
 * The employee list and the new-employee form (plan T6.1 and T6.2), against the real API and a real
 * signed-in Company Admin: the empty company first (summary line, pills, archived list), then adding
 * an employee and the unique-number rule, then the accessibility check. Filters and what each role
 * may see are covered by the API tests and lib/employees/list.test.ts.
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

test("N opens the form; an employee is added and listed; a repeated number is refused", async ({
  page,
}) => {
  await open(page);
  await page.keyboard.press("n");
  await expect(page.getByRole("heading", { level: 1, name: "New employee" })).toBeVisible();
  await page.getByRole("button", { name: "Add employee" }).click();
  await expect(page.getByText("Enter their first name.")).toBeVisible();
  await expect(page.getByText("Choose the hire date.")).toBeVisible();
  await audit(page, "new employee");

  async function fill(number: string) {
    await page.getByLabel("First name", { exact: true }).fill("Ben");
    await page.getByLabel("Last name", { exact: true }).fill("Okafor");
    await page.getByLabel("Work email", { exact: true }).fill("ben@example.com");
    await page.getByLabel("Employee number", { exact: true }).fill(number);
    await page.getByLabel("Hire date", { exact: true }).fill("6 Jan 2025");
    await page.getByRole("button", { name: "Add employee" }).click();
  }
  await fill("E 001");
  await expect(page.getByRole("heading", { level: 1, name: "Employees" })).toBeVisible();
  const grid = page.getByRole("grid", { name: "Employees" });
  await expect(grid.getByText("Ben Okafor")).toBeVisible();
  await expect(page.getByText("1 employee · 1 active", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "New employee" }).click();
  await fill("e001");
  await expect(page.getByText("That employee number is already in use.")).toBeVisible();
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

test("a profile opens from the list, moves through the lifecycle, and then can only be archived", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("button", { name: "New employee" }).click();
  await page.getByLabel("First name", { exact: true }).fill("Cara");
  await page.getByLabel("Last name", { exact: true }).fill("Doyle");
  await page.getByLabel("Work email", { exact: true }).fill("cara@example.com");
  await page.getByLabel("Employee number", { exact: true }).fill("E500");
  await page.getByLabel("Hire date", { exact: true }).fill("6 Jan 2025");
  await page.getByRole("button", { name: "Add employee" }).click();
  await page.getByRole("grid", { name: "Employees" }).getByText("Cara Doyle").dblclick();

  await expect(page.getByRole("heading", { level: 1, name: "Cara Doyle" })).toBeVisible();
  await expect(page.getByText("E500 · Joined 6 Jan 2025")).toBeVisible();
  await expect(page.getByText("Upload the signed agreement first.")).toBeVisible();
  await expect(page.getByRole("switch", { name: /Opted out of the 48-hour week/ })).toBeDisabled();
  await audit(page, "employee profile");

  await page.getByRole("button", { name: "Set to on leave" }).click();
  await page.getByRole("button", { name: "Set to on leave" }).last().click();
  await expect(page.getByText("Currently on leave")).toBeVisible();

  await page.getByText("Advanced: permanently delete this record").click();
  // The move above is history now, so the record can only be archived.
  await expect(page.getByText("This record cannot be deleted")).toBeVisible();
  await expect(page.getByText(/Archive it instead/)).toBeVisible();
});
