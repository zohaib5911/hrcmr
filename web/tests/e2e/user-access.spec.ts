/**
 * The User Access list (plan T5.1), against the real API and a real signed-in Company Admin: the
 * admin is listed (marked "you"), the unlinked banner counts them, the filters work, and the page
 * passes the accessibility check in both themes at phone and desktop widths.
 */
import { expect, test } from "../support/fixtures";

import { audit } from "../support/axe";
import { MAILPIT } from "../support/accounts";

async function open(page: import("@playwright/test").Page) {
  await page.goto("/company/users");
  await expect(page.getByRole("heading", { level: 1, name: "User access" })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("the admin is listed, the banner counts unlinked users, and the filters narrow the list", async ({
  page,
}) => {
  await open(page);
  const table = page.getByRole("grid", { name: "People with access" });
  await expect(table.getByText("Amira Hassan")).toBeVisible();
  await expect(table.getByText("(you)")).toBeVisible();
  await expect(table.getByText("Company Admin")).toBeVisible();
  await expect(page.getByRole("alert").getByText("1 unlinked user")).toBeVisible();
  await expect(page.getByText("1 row", { exact: true })).toBeVisible();

  await page.getByLabel("Role", { exact: true }).selectOption("employee");
  await expect(page.getByText("Nobody matches")).toBeVisible();
  await page.getByLabel("Role", { exact: true }).selectOption("all");
  await page.getByRole("searchbox", { name: "Search people" }).fill("hassan");
  await expect(table.getByText("Amira Hassan")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search people" }).fill("zzz");
  await expect(page.getByText("Nobody matches")).toBeVisible();
});

test("an invitation is sent, shown as invited, resent and cancelled", async ({ page, request }) => {
  await open(page);
  await page.getByRole("button", { name: "Invite user" }).click();
  const sheet = page.getByRole("dialog", { name: "Invite user" });
  await sheet.getByRole("button", { name: "Send invitation" }).click();
  await expect(sheet.getByText("Enter their first name.")).toBeVisible();
  await audit(page, "invite sheet", { modal: true });

  const email = `nia-${Date.now()}@example.com`;
  await sheet.getByLabel("First name", { exact: true }).fill("Nia");
  await sheet.getByLabel("Last name", { exact: true }).fill("Clarke");
  await sheet.getByLabel("Work email", { exact: true }).fill(email);
  await sheet.getByRole("radio", { name: /Recruiter/ }).click();
  await sheet.getByRole("button", { name: "Send invitation" }).click();

  const grid = page.getByRole("grid", { name: "People with access" });
  await expect(grid.getByText("Nia Clarke")).toBeVisible();
  await expect(grid.getByText("Invited", { exact: true })).toBeVisible();
  await expect
    .poll(async () => {
      const found = await request.get(`${MAILPIT}/api/v1/search`, {
        params: { query: `to:${email} subject:"You have been invited"` },
      });
      return ((await found.json()) as { messages: unknown[] }).messages.length;
    })
    .toBe(1);

  await page.getByRole("button", { name: "Actions for Nia Clarke" }).click();
  await page.getByRole("menuitem", { name: "Resend invitation" }).click();
  await expect(page.getByText(`Invitation sent to ${email}`, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Actions for Nia Clarke" }).click();
  await page.getByRole("menuitem", { name: "Cancel invitation" }).click();
  const confirm = page.getByRole("dialog", { name: /Cancel the invitation for Nia Clarke/ });
  await confirm.getByRole("button", { name: "Cancel invitation" }).click();
  await expect(grid.getByText("Nia Clarke")).toHaveCount(0);
});

test("the policy cards are there, and the role viewer lists what a role can do", async ({
  page,
}) => {
  await open(page);
  const policy = page.getByRole("radiogroup", { name: "Two-step verification policy" });
  await expect(policy.getByRole("radio", { name: /Optional for everyone/ })).toBeChecked();
  await expect(policy.getByRole("radio", { name: /Required for all users/ })).toBeEnabled();

  await page.getByRole("button", { name: "What can each role do?" }).click();
  const sheet = page.getByRole("dialog", { name: "What can each role do?" });
  await expect(sheet.getByText("Full control", { exact: false })).toBeVisible();
  await sheet.getByLabel("Role", { exact: true }).selectOption("employee");
  await expect(sheet.getByText("See their own profile")).toBeVisible();
  await expect(sheet.getByText("Add and change company profile")).toHaveCount(0);
  await audit(page, "role viewer", { modal: true });
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of [390, 1280] as const) {
      test(`the page at ${width} px has no sideways scroll and passes axe`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await audit(page, `${colorScheme} user access ${width}px`);
      });
    }
  });
}
