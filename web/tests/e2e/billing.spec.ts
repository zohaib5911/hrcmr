/**
 * T16.3 (plan 8.16): the billing page, through the real screens and the real API, for a paid and a free
 * Company Admin. Nothing here calls Stripe: the cancel dialog is opened and closed, never confirmed.
 */
import { request as playwrightRequest } from "@playwright/test";

import { createSignedInAdmin, newAccount } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

test("a paid company sees its plan and can open the cancel dialog without cancelling", async ({
  page,
}) => {
  await page.goto("/company/billing");
  await expect(page.getByRole("heading", { level: 1, name: "Billing" })).toBeVisible();
  // The plan name appears more than once on the page; the first match is enough here.
  await expect(page.getByText("1 year plan", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Cancel subscription" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Cancel your subscription?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).toHaveCount(0);

  await audit(page, "billing paid plan");
});

test("a free company sees the Free plan", async ({ browser }) => {
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api, newAccount("billing-free"), { plan: "free" });
  const context = await browser.newContext({ storageState: await api.storageState() });
  const page = await context.newPage();

  await page.goto("/company/billing");
  await expect(page.getByRole("heading", { level: 1, name: "Billing" })).toBeVisible();
  await expect(page.getByText("Free", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel subscription" })).toHaveCount(0);

  await context.close();
  await api.dispose();
});
