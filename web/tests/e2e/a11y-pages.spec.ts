/**
 * T22.3 accessibility audit (plan L1500): axe (WCAG 2.2 AA + best practice, tests/support/axe.ts) finds
 * nothing on every page of the app, the sign-in pages and the public site, in both themes; the main
 * flows hold up for a screen reader (landmarks, one heading, a skip link, named controls); and with
 * reduced motion nothing slides or zooms. The /design components are covered by design-a11y.spec.ts.
 */
import { request as playwrightRequest, type Page } from "@playwright/test";

import { API, createSignedInAdmin, csrfHeaders } from "../support/accounts";
import { audit } from "../support/axe";
import { expect, test } from "../support/fixtures";

/** Every signed-in page that takes no id. */
const APP_PAGES = [
  "/dashboard",
  "/employees",
  "/employees/new",
  "/employees/archived",
  "/organogram",
  "/documents",
  "/my-documents",
  "/attendance",
  "/attendance/absences",
  "/attendance/bulk",
  "/attendance/import",
  "/attendance/timesheets",
  "/clock",
  "/work-log",
  "/my-work-log",
  "/leave",
  "/leave/settings",
  "/leave/year-end",
  "/my-leave",
  "/my-approvals",
  "/holiday-management",
  "/rota",
  "/rota/settings",
  "/my-shifts",
  "/learning",
  "/learning/my",
  "/policies",
  "/recruitment",
  "/reports",
  "/profile",
  "/sponsor-compliance",
  "/sponsor-compliance/migrant-employees",
  "/sponsor-compliance/change-of-circumstances",
  "/sponsor-compliance/reminders",
  "/sponsor-compliance/dossier",
  "/sponsorship-checker",
  "/company",
  "/company/users",
  "/company/locations",
  "/company/departments",
  "/company/designations",
  "/company/key-personnel",
  "/company/working-pattern",
  "/company/trading-hours",
  "/company/pay-bands",
  "/company/pay-schedules",
  "/company/payment-types",
  "/company/tax-codes",
  "/company/bank-accounts",
  "/company/compliance-documents",
  "/company/billing",
  "/company/delete-account",
] as const;

/** Signed-out pages not already audited by marketing-pages.spec.ts or auth-pages.spec.ts. */
const PUBLIC_PAGES = [
  "/login",
  "/forgot-password",
  "/verify",
  "/legal/privacy",
  "/legal/terms",
  "/resources",
  "/resources/guides",
  "/resources/templates",
  "/resources/tools",
  "/resources/tools/holiday-entitlement-calculator",
  "/resources/tools/ilr-citizenship-checker",
  "/resources/tools/right-to-work-october-2026-checker",
  "/resources/tools/risk-assessment-template",
  "/resources/tools/skilled-worker-ilr-salary-calculator",
  "/resources/tools/skilled-worker-visa-checker",
  "/resources/tools/sponsor-licence-cost-calculator",
  "/resources/tools/sponsor-reporting-deadline-calculator",
  "/resources/tools/sponsorship-job-checker",
  "/resources/tools/uk-employer-cost-calculator",
  "/resources/tools/uk-minimum-wage-underpayment-checker",
  "/resources/tools/uk-notice-pay-calculator",
  "/resources/tools/uk-redundancy-pay-calculator",
  "/resources/tools/uk-sick-pay-calculator",
  "/resources/tools/uk-take-home-salary-calculator",
  "/sponsors",
  "/sponsors/changes",
  "/sponsors/methodology",
  "/sponsors/terms",
] as const;

/** Opens a page and waits until its main heading is on screen. */
async function open(page: Page, path: string) {
  const response = await page.goto(path);
  expect(response?.status(), path).toBeLessThan(400);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  // Axe reads what is on screen: wait for the data, not a loading skeleton or a half-enabled control.
  await expect(page.locator(".skeleton"), path).toHaveCount(0);
  // ...and for the page's own requests, which disable its controls while they run (busy).
  await page.waitForLoadState("networkidle");
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test("every signed-in page passes axe", async ({ page }) => {
      test.setTimeout(APP_PAGES.length * 15_000);
      for (const path of APP_PAGES) {
        await open(page, path);
        await audit(page, `${colorScheme} ${path}`);
      }
    });

    test("an employee's profile passes axe", async ({ page }) => {
      const made = await page.request.post(`${API}/employees`, {
        headers: await csrfHeaders(page.request),
        data: {
          first_name: "Alma",
          last_name: "Reyes",
          email: `alma.${colorScheme}@example.com`,
          employee_number: `A11Y-${colorScheme}`,
          hire_date: "2025-01-06",
        },
      });
      expect(made.status(), await made.text()).toBe(201);
      const { id } = (await made.json()) as { id: string };
      await open(page, `/employees/${id}`);
      await audit(page, `${colorScheme} employee profile`);
    });

    test.describe("signed out", () => {
      test.use({ storageState: { cookies: [], origins: [] } });

      test("every public page passes axe", async ({ page }) => {
        test.setTimeout(PUBLIC_PAGES.length * 15_000);
        for (const path of PUBLIC_PAGES) {
          await open(page, path);
          await audit(page, `${colorScheme} ${path}`);
        }
      });
    });
  });
}

/** What a screen reader meets first on the main flows: a skip link, the landmarks, one h1, named controls. */
const MAIN_FLOWS = ["/dashboard", "/employees", "/my-leave", "/rota", "/sponsor-compliance"];

test("the main flows read well with a screen reader", async ({ page }) => {
  for (const path of MAIN_FLOWS) {
    await open(page, path);
    await expect(page.getByRole("main"), path).toHaveCount(1);
    await expect(page.getByRole("navigation").first(), path).toBeAttached();
    await expect(page.getByRole("heading", { level: 1 }), path).toHaveCount(1);

    // The first Tab lands on a skip link, and following it puts focus in the main content.
    await page.locator("body").press("Tab");
    const skip = page.locator(":focus");
    await expect(skip, path).toHaveAccessibleName(/skip/i);
    await skip.press("Enter");
    expect(
      await page.evaluate(() => Boolean(document.activeElement?.closest("main, #main"))),
      path,
    ).toBe(true);

    // In the accessibility tree a screen reader reads, every control has a name to announce.
    const tree = await page.locator("body").ariaSnapshot();
    const unnamed = tree
      .split("\n")
      .filter((line) =>
        /^\s*- (button|link|switch|checkbox|radio|textbox|combobox|tab|menuitem)\s*(\[|:|$)/.test(
          line,
        ),
      );
    expect(unnamed, path).toEqual([]);
  }
});

test("a new employee can be added with only a keyboard", async ({ page }) => {
  await open(page, "/employees/new");
  const first = page.getByRole("textbox", { name: "First name", exact: true });
  await first.focus();
  await expect(first).toBeFocused();
  await first.fill("Kofi");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("textbox", { name: "Last name", exact: true })).toBeFocused();
});

test("with reduced motion nothing slides or zooms", async ({ browser }) => {
  // A fresh context so the media setting applies from the first paint.
  const api = await playwrightRequest.newContext();
  await createSignedInAdmin(api);
  const context = await browser.newContext({
    storageState: await api.storageState(),
    reducedMotion: "reduce",
  });
  await api.dispose();
  const page = await context.newPage();

  // Every finite animation on the page, shown at its first and last frame: does anything move?
  const moving = () =>
    page.evaluate(() => {
      const pose = (el: Element) => {
        const style = getComputedStyle(el);
        return [style.transform, style.translate, style.scale, style.rotate].join(" ");
      };
      return document
        .getAnimations()
        .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
        .filter((animation) => {
          const target = (animation.effect as KeyframeEffect | null)?.target;
          const end = Number(animation.effect?.getComputedTiming().endTime ?? 0);
          if (!target || end <= 0) return false;
          const now = animation.currentTime;
          animation.pause();
          animation.currentTime = 0;
          const first = pose(target);
          animation.currentTime = end - 1;
          const last = pose(target);
          animation.currentTime = now;
          animation.play();
          return first !== last;
        })
        .map((animation) => (animation as CSSAnimation).animationName ?? "animation");
    });

  await open(page, "/dashboard");
  expect(await moving()).toEqual([]);
  expect(
    await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--motion-distance").trim(),
    ),
  ).toBe("0px");

  // An overlay opening is the main place things move: the command palette.
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByRole("dialog").first()).toBeVisible();
  expect(await moving()).toEqual([]);
  await context.close();
});
