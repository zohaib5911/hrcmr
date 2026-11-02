/**
 * Locations, departments and designations (plan T4.2), against the real API and a real signed-in
 * Company Admin. The tests run in order, because each builds on what the one before made; the postcode
 * lookup (a public service) is covered by the API tests, not clicked here.
 */
import { expect, test, type Page } from "@playwright/test";

import { audit } from "../support/axe";

test.describe.configure({ mode: "serial" });

async function open(page: Page, path: string, heading: string) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

const sheet = (page: Page, name: string) => page.getByRole("dialog", { name });

test("job titles need a department first, and the page says so", async ({ page }) => {
  await open(page, "/company/designations", "Designations");
  await expect(
    page.getByText("Job titles sit in departments, so add a department first."),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Add a department" })).toHaveAttribute(
    "href",
    "/company/departments",
  );
  await expect(page.getByRole("button", { name: "Add job title" })).toHaveCount(0);
});

test("departments: add, refuse a repeat, rename", async ({ page }) => {
  await open(page, "/company/departments", "Departments");
  await expect(page.getByText("No departments yet")).toBeVisible();
  await page.getByRole("button", { name: "Add department" }).first().click();
  await sheet(page, "Add department").getByLabel("Name", { exact: true }).fill("Care");
  await sheet(page, "Add department").getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Department added").first()).toBeVisible();
  const row = page.getByRole("button", { name: /^Care\b/ });
  await expect(row).toContainText("0 job titles");

  await page.getByRole("button", { name: "Add department" }).click();
  await sheet(page, "Add department").getByLabel("Name", { exact: true }).fill("care");
  await sheet(page, "Add department").getByRole("button", { name: "Save" }).click();
  await expect(
    sheet(page, "Add department").getByText("You already have a department with that name."),
  ).toBeVisible();
  await sheet(page, "Add department").getByRole("button", { name: "Cancel" }).click();

  await row.click();
  await sheet(page, "Rename department").getByLabel("Name", { exact: true }).fill("Care team");
  await sheet(page, "Rename department").getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: /^Care team\b/ })).toBeVisible();
});

test("designations: add a title with a SOC code, refuse a bad code, and a department with titles stays", async ({
  page,
}) => {
  await open(page, "/company/designations", "Designations");
  await page.getByRole("button", { name: "Add job title" }).first().click();
  const form = sheet(page, "Add job title");
  await form.getByLabel("Job title", { exact: true }).fill("Senior care worker");
  await form.getByLabel("SOC code (optional)", { exact: true }).fill("12");
  await form.getByRole("button", { name: "Save" }).click();
  await expect(form.getByText("A SOC code is 4 digits, such as 2231.")).toBeVisible();
  await form.getByLabel("SOC code (optional)", { exact: true }).fill("6135");
  await form.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Job title added").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Care team" })).toContainText("Senior care worker");
  await expect(page.getByRole("region", { name: "Care team" })).toContainText("SOC 6135");

  await open(page, "/company/departments", "Departments");
  await page.getByRole("button", { name: /^Care team\b/ }).click();
  await sheet(page, "Rename department").getByRole("button", { name: "Archive" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Archive" }).click();
  await expect(page.getByText("Archive or move this department's job titles first.")).toBeVisible();
});

test("locations: the first is the main one, a new main one takes over, and one can be archived", async ({
  page,
}) => {
  await open(page, "/company/locations", "Locations");
  await expect(page.getByText("No locations yet")).toBeVisible();
  async function add(name: string, main: boolean) {
    await page.getByRole("button", { name: "Add location" }).first().click();
    const form = sheet(page, "Add location");
    await form.getByLabel("Name", { exact: true }).fill(name);
    await form.getByLabel("Postcode", { exact: true }).fill("sw1a1aa");
    await form.getByLabel("Address line 1", { exact: true }).fill("1 Quay Street");
    await form.getByLabel("Town or city", { exact: true }).fill("London");
    if (main) await form.getByRole("switch", { name: /main location/ }).click();
    await form.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Location added").first()).toBeVisible();
  }
  await add("Head office", false);
  await expect(page.getByRole("button", { name: /Head office/ })).toContainText("Main");
  await expect(page.getByRole("button", { name: /Head office/ })).toContainText("SW1A 1AA, London");
  await add("Depot", true);
  await expect(page.getByRole("button", { name: /Depot/ })).toContainText("Main");
  await expect(page.getByRole("button", { name: /Head office/ })).not.toContainText("Main");

  await page.getByRole("button", { name: /Head office/ }).click();
  await sheet(page, "Edit location").getByRole("button", { name: "Archive" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Archive" }).click();
  await expect(page.getByText("Location archived").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Head office/ })).toHaveCount(0);

  await open(page, "/company", "Company");
  await expect(page.getByRole("link", { name: /^Locations/ })).toContainText("1");
  await expect(page.getByRole("link", { name: /^Departments/ })).toContainText("1");
  await expect(page.getByRole("link", { name: /^Designations/ })).toContainText("1");
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const [path, heading] of [
      ["/company/locations", "Locations"],
      ["/company/departments", "Departments"],
      ["/company/designations", "Designations"],
    ] as const) {
      for (const width of [390, 1280] as const) {
        test(`${heading} at ${width} px passes axe, and its sheet too`, async ({ page }) => {
          await page.setViewportSize({ width, height: 900 });
          await open(page, path, heading);
          const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          );
          expect(overflow).toBeLessThanOrEqual(0);
          await audit(page, `${colorScheme} ${heading} ${width}px`);
          await page.getByRole("button", { name: /^Add / }).first().click();
          await expect(page.getByRole("dialog")).toBeVisible();
          await page.waitForTimeout(500);
          await audit(page, `${colorScheme} ${heading} sheet ${width}px`, { modal: true });
        });
      }
    }
  });
}
