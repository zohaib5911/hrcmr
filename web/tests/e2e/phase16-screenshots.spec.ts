/** Phase 16 gate: the billing page and the delete-account page at 390/1280 px in light and dark. */
import path from "node:path";

import { request as playwrightRequest, type Browser, type Page } from "@playwright/test";

import {
  API,
  createSignedInAdmin,
  csrfHeaders,
  newAccount,
  waitForMail,
} from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-16");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");

async function shoot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  await audit(page, name);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

/** A new Company Admin's page. With `scheduled`, the deletion is already confirmed (7 days on). */
async function adminPage(
  browser: Browser,
  { plan, scheduled = false }: { plan: "free" | "annual"; scheduled?: boolean },
) {
  const api = await playwrightRequest.newContext();
  const account = await createSignedInAdmin(api, newAccount("phase16"), { plan });
  if (scheduled) {
    const steppedUp = await api.post(`${API}/auth/step-up`, {
      headers: await csrfHeaders(api),
      data: { password: account.password },
    });
    expect(steppedUp.status(), await steppedUp.text()).toBe(200);
    const started = await api.post(`${API}/companies/me/deletion-request`, {
      headers: await csrfHeaders(api),
      data: { export_requested: false },
    });
    expect(started.status(), await started.text()).toBe(202);
    const mail = await waitForMail(api, account.email, "Your confirmation code");
    const code = (/Your code: (\d{3} \d{3})/.exec(mail)?.[1] ?? "").replace(" ", "");
    const confirmed = await api.post(`${API}/companies/me/deletion-request/confirm`, {
      headers: await csrfHeaders(api),
      data: { code },
    });
    expect(confirmed.status(), await confirmed.text()).toBe(200);
  }
  const context = await browser.newContext({ storageState: await api.storageState() });
  await api.dispose();
  return { context, page: await context.newPage() };
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`Billing, paid plan, at ${width}px`, async ({ browser }) => {
        test.setTimeout(180_000);
        const { context, page } = await adminPage(browser, { plan: "annual" });
        try {
          await page.setViewportSize({ width, height: 900 });
          await page.goto("/company/billing");
          await expect(page.getByRole("heading", { level: 1, name: "Billing" })).toBeVisible();
          await expect(page.getByText("1 year plan", { exact: true }).first()).toBeVisible();
          await page.waitForLoadState("networkidle");
          await shoot(page, `billing-paid-${colorScheme}-${width}`);
        } finally {
          await context.close();
        }
      });

      test(`Billing, free plan, at ${width}px`, async ({ browser }) => {
        test.setTimeout(180_000);
        const { context, page } = await adminPage(browser, { plan: "free" });
        try {
          await page.setViewportSize({ width, height: 900 });
          await page.goto("/company/billing");
          await expect(page.getByRole("heading", { level: 1, name: "Billing" })).toBeVisible();
          await page.waitForLoadState("networkidle");
          await shoot(page, `billing-free-${colorScheme}-${width}`);
        } finally {
          await context.close();
        }
      });

      test(`Delete account, before any request, at ${width}px`, async ({ browser }) => {
        test.setTimeout(180_000);
        const { context, page } = await adminPage(browser, { plan: "annual" });
        try {
          await page.setViewportSize({ width, height: 900 });
          await page.goto("/company/delete-account");
          await expect(
            page.getByRole("heading", { level: 1, name: "Delete company account" }),
          ).toBeVisible();
          await page.waitForLoadState("networkidle");
          await shoot(page, `delete-empty-${colorScheme}-${width}`);
        } finally {
          await context.close();
        }
      });

      test(`Delete account, scheduled, at ${width}px`, async ({ browser }) => {
        test.setTimeout(180_000);
        const { context, page } = await adminPage(browser, { plan: "annual", scheduled: true });
        try {
          await page.setViewportSize({ width, height: 900 });
          await page.goto("/company/delete-account");
          await expect(
            page.locator("#main").getByText("This account will be deleted on"),
          ).toBeVisible();
          await page.waitForLoadState("networkidle");
          await shoot(page, `delete-scheduled-${colorScheme}-${width}`);
        } finally {
          await context.close();
        }
      });
    }
  });
}
