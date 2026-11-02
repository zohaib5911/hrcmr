/**
 * The employee list and the new-employee form (plan T6.1 and T6.2), against the real API and a real
 * signed-in Company Admin: the empty company first (summary line, pills, archived list), then adding
 * an employee and the unique-number rule, then the accessibility check. Filters and what each role
 * may see are covered by the API tests and lib/employees/list.test.ts.
 */
import { request as playwrightRequest } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders, newAccount } from "../support/accounts";
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

test("the Personal tab saves details, an address and a contact, and shows identity only after a password check", async ({
  browser,
}) => {
  // Its own administrator, so the test knows the password the step-up check asks for.
  const account = newAccount("personal");
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, account);
  const made = await api.post(`${API}/employees`, {
    headers: await csrfHeaders(api),
    data: {
      first_name: "Dina",
      last_name: "Frost",
      email: "dina@example.com",
      employee_number: "P100",
      hire_date: "2025-01-06",
    },
  });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const context = await browser.newContext({ storageState: await api.storageState() });
  await api.dispose();
  const page = await context.newPage();

  await open(page, `/employees/${id}`, "Dina Frost");
  await page.getByRole("tab", { name: "Personal" }).click();

  await page.getByRole("button", { name: "Edit details" }).click();
  await page.getByLabel("Nationality", { exact: true }).fill("British");
  await page.getByLabel("Marital status", { exact: true }).selectOption("civil_partnership");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Details saved").first()).toBeVisible();
  await expect(page.getByText("Civil partnership")).toBeVisible();
  await expect(page.getByText("British")).toBeVisible();

  await page.getByRole("button", { name: "Add address" }).click();
  await page.getByLabel("Address line 1", { exact: true }).fill("1 High Street");
  await page.getByLabel("Town and county", { exact: true }).fill("Leeds");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("1 High Street, Leeds")).toBeVisible();

  await page.getByRole("button", { name: "Add contact" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Sam Frost");
  await page.getByLabel("Relationship", { exact: true }).selectOption("civil_partner");
  await page.getByLabel("Phone", { exact: true }).fill("07700 900456");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Civil partner · 07700 900456")).toBeVisible();

  // Identity: editing needs the password; afterwards it shows masked, and "Show" needs no second check.
  await page
    .getByRole("region", { name: "National Insurance and passport" })
    .getByRole("button", { name: "Edit" })
    .click();
  await page.getByLabel("Your password", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Confirm" }).click();
  await page.getByLabel("National Insurance number", { exact: true }).fill("AB 12 34 56 C");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("•• •• •• 56 C")).toBeVisible();
  await expect(page.getByText("AB 12 34 56 C")).toHaveCount(0);
  await page
    .getByRole("region", { name: "National Insurance and passport" })
    .getByRole("button", { name: "Show" })
    .click();
  await expect(page.getByText("AB 12 34 56 C")).toBeVisible();
  await expect(page.getByText(/recorded in the audit trail/)).toBeVisible();
  await audit(page, "personal tab");
  await context.close();
});
