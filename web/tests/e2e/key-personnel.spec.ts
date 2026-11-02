/**
 * Key personnel (plan T4.3), against the real API and a real signed-in Company Admin. The identity
 * document goes through the file store and the virus scanner, which the API tests cover; here the
 * roles, "same as the Authorising Officer", the count, and the page's accessibility are checked.
 */
import { expect, test, type Page } from "@playwright/test";

import { audit } from "../support/axe";

test.describe.configure({ mode: "serial" });

async function open(page: Page) {
  await page.goto("/company/key-personnel");
  await expect(page.getByRole("heading", { level: 1, name: "Key personnel" })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

const sheet = (page: Page, name: RegExp) => page.getByRole("dialog", { name });

test("the four roles, each explained, with nobody added yet", async ({ page }) => {
  await open(page);
  await expect(page.getByText("0 of 4 roles filled")).toBeVisible();
  for (const title of ["Authorising Officer", "Key Contact", "Level 1 User", "Level 2 Users"]) {
    await expect(page.getByRole("region", { name: title })).toContainText("Nobody added yet");
  }
  await expect(page.getByRole("region", { name: "Key Contact" })).toContainText(
    "The person the Home Office contacts about the licence.",
  );
});

test("a Key Contact cannot be the same as an officer who is not there yet", async ({ page }) => {
  await open(page);
  await page
    .getByRole("region", { name: "Key Contact" })
    .getByRole("button", { name: "Add" })
    .click();
  const form = sheet(page, /Add Key Contact/);
  await expect(
    form.getByRole("switch", { name: /Same person as the Authorising Officer/ }),
  ).toBeDisabled();
  await expect(form.getByText("Add the Authorising Officer first.")).toBeVisible();
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await expect(form.getByText("Enter a first name.")).toBeVisible();
  await form.getByRole("button", { name: "Cancel" }).click();
});

test("add the officer, then a Key Contact who is the same person, and count the roles", async ({
  page,
}) => {
  await open(page);
  await page
    .getByRole("region", { name: "Authorising Officer" })
    .getByRole("button", { name: "Add" })
    .click();
  const officer = sheet(page, /Add Authorising Officer/);
  await expect(officer.getByRole("switch", { name: /Same person/ })).toHaveCount(0);
  await officer.getByLabel("First name", { exact: true }).fill("Amira");
  await officer.getByLabel("Last name", { exact: true }).fill("Hassan");
  await officer.getByLabel("Job title", { exact: true }).fill("Director");
  await officer.getByLabel("Email", { exact: true }).fill("not-an-email");
  await officer.getByRole("button", { name: "Save", exact: true }).click();
  await expect(officer.getByText(/valid email|not a valid|email address/i)).toBeVisible();
  await officer.getByLabel("Email", { exact: true }).fill("amira@example.com");
  await officer.getByRole("radio", { name: "Yes" }).click();
  await officer.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("region", { name: "Authorising Officer" })).toContainText(
    "Amira Hassan",
  );

  await page
    .getByRole("region", { name: "Key Contact" })
    .getByRole("button", { name: "Add" })
    .click();
  const contact = sheet(page, /Add Key Contact/);
  await contact.getByRole("switch", { name: /Same person/ }).click();
  await expect(contact.getByLabel("First name", { exact: true })).toHaveCount(0);
  await contact.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("region", { name: "Key Contact" })).toContainText("Amira Hassan");

  // Two Level 2 Users are allowed; the other roles hold one person each.
  for (const first of ["Una", "Vic"]) {
    await page
      .getByRole("region", { name: "Level 2 Users" })
      .getByRole("button", { name: "Add" })
      .first()
      .click();
    const form = sheet(page, /Add Level 2 User/);
    await form.getByLabel("First name", { exact: true }).fill(first);
    await form.getByLabel("Last name", { exact: true }).fill("Okafor");
    await form.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByRole("region", { name: "Level 2 Users" })).toContainText(first);
  }
  await page.reload();
  await expect(page.getByText("3 of 4 roles filled")).toBeVisible();

  await page.goto("/company");
  await expect(
    page
      .getByRole("button", { name: /^Key personnel/ })
      .or(page.getByRole("link", { name: /^Key personnel/ })),
  ).toContainText("3 of 4");
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const width of [390, 1280] as const) {
      test(`the page at ${width} px passes axe, and so does a person's sheet`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        await audit(page, `${colorScheme} key personnel ${width}px`);
        await page
          .getByRole("button", { name: /Amira Hassan/ })
          .first()
          .click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await page.waitForTimeout(500);
        await audit(page, `${colorScheme} key personnel sheet ${width}px`, { modal: true });
      });
    }
  });
}
