/**
 * T16.5 (plan 8.16): deleting the company account, through the real screens and the real API. A Company
 * Admin asks, the 6-digit code arrives in Mailpit, entering it schedules the deletion 7 days on, and
 * withdrawing clears the schedule. The purge never runs here: it is an hour after the 7 days.
 */
import { request as playwrightRequest } from "@playwright/test";

import { createSignedInAdmin, newAccount, waitForMail } from "../../support/accounts";
import { expect, test } from "../../support/fixtures";

const dateAfter = (days: number) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/London",
  }).format(new Date(Date.now() + days * 86_400_000));

test("a Company Admin asks, confirms with the e-mailed code, then withdraws the deletion", async ({
  browser,
}) => {
  const api = await playwrightRequest.newContext();
  const account = await createSignedInAdmin(api, newAccount("deletion"));
  const context = await browser.newContext({ storageState: await api.storageState() });
  const page = await context.newPage();

  await test.step("ask for the deletion; the code goes to the admin's e-mail", async () => {
    await page.goto("/company/delete-account");
    await expect(
      page.getByRole("heading", { level: 1, name: "Delete company account" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Delete company account" }).click();
    const dialog = page.getByRole("alertdialog");
    await dialog
      .getByLabel(`Type ${account.company} to confirm`, { exact: true })
      .fill(account.company);
    await dialog.getByRole("button", { name: "Send the code" }).click();
    await page.getByLabel("Your password", { exact: true }).fill(account.password);
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await expect(page.getByLabel("Code", { exact: true })).toBeVisible();
  });

  await test.step("the code in the e-mail schedules the deletion 7 days on", async () => {
    const mail = await waitForMail(api, account.email, "Your confirmation code");
    // The e-mail shows the code as "123 456"; the page takes it with or without the space.
    const code = (/Your code: (\d{3} \d{3})/.exec(mail)?.[1] ?? "").replace(" ", "");
    expect(code).toMatch(/^\d{6}$/);
    await page.getByLabel("Code", { exact: true }).fill(code);
    await page.getByRole("button", { name: "Confirm deletion" }).click();
    await expect(page.getByText("This account will be deleted on")).toBeVisible();
    await expect(page.getByText(`This account will be deleted on ${dateAfter(7)}`)).toBeVisible();
  });

  await test.step("an admin withdraws the request and the schedule clears", async () => {
    await page.getByRole("button", { name: "Withdraw deletion request" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Withdraw request" }).click();
    await expect(page.getByText("This account will be deleted on")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Delete company account" })).toBeVisible();
  });

  await context.close();
  await api.dispose();
});
