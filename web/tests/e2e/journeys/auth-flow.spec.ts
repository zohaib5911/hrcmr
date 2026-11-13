/**
 * The Phase 3 flow, through the real screens and the real API (plan: "signup, verify (Mailpit),
 * dashboard, logout, login with MFA, recovery code login, password reset"). Mailpit holds the e-mails.
 */
import { expect, test, type Page } from "@playwright/test";

import { newAccount, tokenIn, waitForMail } from "../../support/accounts";
import { totp } from "../../support/totp";

test.use({ storageState: { cookies: [], origins: [] } });

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

test("sign up, confirm, set up two-step, sign in with a code and a recovery code, reset the password", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const account = newAccount("flow");
  let secret = "";
  let recoveryCode = "";
  const newPassword = `${account.password} renewed`;

  await test.step("sign up and see the check-your-inbox screen", async () => {
    await page.goto("/setup");
    await page.getByLabel("Company name", { exact: true }).fill(account.company);
    await page.getByRole("radio", { name: /Scotland/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("First name", { exact: true }).fill("Amira");
    await page.getByLabel("Last name", { exact: true }).fill("Hassan");
    await page.getByLabel("Work email", { exact: true }).fill(account.email);
    await page.getByLabel("Password", { exact: true }).fill(account.password);
    await page.getByRole("checkbox").click();
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Check your inbox" })).toBeVisible();
    await expect(page.getByText(account.email)).toBeVisible();
  });

  await test.step("the e-mailed link confirms the address and opens the dashboard", async () => {
    const mail = await waitForMail(page.request, account.email, "Confirm your email address");
    await page.goto(`/verify-email?token=${tokenIn(mail, "/verify-email")}`);
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await expect(page.locator("#app-sidebar").getByText(account.company)).toBeVisible();
    await expect(page.getByText("You're on the free plan")).toBeVisible();
  });

  await test.step("set up two-step verification and keep the recovery codes", async () => {
    await page.goto("/mfa/enrol");
    const key = page.getByText(/^[A-Z2-7]{4}( [A-Z2-7]{4})+$/);
    await expect(key).toBeVisible();
    secret = ((await key.textContent()) ?? "").replace(/\s/g, "");
    await page.getByLabel("6-digit code", { exact: true }).fill(totp(secret));
    await page.getByRole("button", { name: "Confirm" }).click();
    const codes = page.getByRole("list", { name: "Recovery codes" }).getByRole("listitem");
    await expect(codes).toHaveCount(10);
    recoveryCode = ((await codes.first().textContent()) ?? "").trim();
    await page.getByRole("button", { name: "I've saved them" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await signOut(page);
  });

  await test.step("sign in with the password and the code from the app", async () => {
    await signIn(page, account.email, account.password);
    await expect(
      page.getByRole("heading", { level: 1, name: "Two-step verification" }),
    ).toBeVisible();
    // The next 30-second step: the one used to set up cannot be used again.
    await page.getByLabel("6-digit code", { exact: true }).fill(totp(secret, 1));
    await page.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await signOut(page);
  });

  await test.step("sign in with a recovery code, which works once", async () => {
    await signIn(page, account.email, account.password);
    await page.getByRole("button", { name: "Use a recovery code" }).click();
    await page.getByLabel("Recovery code", { exact: true }).fill(recoveryCode);
    await page.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    await signOut(page);
  });

  await test.step("reset the forgotten password from the e-mailed link", async () => {
    await page.goto("/forgot-password");
    await page.getByLabel("Email address", { exact: true }).fill(account.email);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByText("Check your inbox")).toBeVisible();
    const mail = await waitForMail(page.request, account.email, "Reset your password");
    await page.goto(`/reset-password?token=${tokenIn(mail, "/reset-password")}`);
    await page.getByLabel("New password", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Change password" }).click();
    await expect(page.getByText("Your password has been changed")).toBeVisible();

    // The old password no longer works; the new one gets as far as the second step.
    await signIn(page, account.email, account.password);
    await expect(page.getByRole("region", { name: "Sign in" }).getByRole("alert")).toContainText(
      "That email and password do not match.",
    );
    await signIn(page, account.email, newPassword);
    await expect(
      page.getByRole("heading", { level: 1, name: "Two-step verification" }),
    ).toBeVisible();
  });
});
