/** Phase 17 screenshots: admin screens and tenant banners, both widths and themes. */
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { API, csrfHeaders } from "../support/accounts";
import { ADMIN_ORIGIN, signInPlatformAdmin } from "../support/platform";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-17");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");
async function shoot(page: Page, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  // Assert styles loaded as well as markup: an unstyled admin-host image is not design evidence.
  expect(await page.locator("body").evaluate((el) => getComputedStyle(el).fontFamily)).not.toBe(
    '"Times New Roman"',
  );
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
}
for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`admin screens and tenant banners at ${width}px`, async ({ page }) => {
        test.setTimeout(180_000);
        // Production CSP upgrades admin-host assets to HTTPS, absent on the local test server.
        // Relay only static CSS/fonts; scripts remain blocked and admin actions remain unit tests.
        await page.route("https://admin.example.test:3100/_next/static/**", async (route) => {
          if (!["stylesheet", "font"].includes(route.request().resourceType()))
            return route.abort();
          const asset = await page.request.get(
            route.request().url().replace("https://admin.example.test", "http://127.0.0.1"),
          );
          await route.fulfill({ response: asset });
        });
        const account = await signInPlatformAdmin(page, "owner");
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        // Admin-host client JavaScript remains unavailable under the recorded local CSP limitation.
        for (const [route, heading, name] of [
          ["/", "Platform admin", "overview"],
          ["/companies", "Companies", "companies"],
          ["/users", "Users", "users"],
          ["/subscriptions", "Subscriptions", "subscriptions"],
          ["/queues", "Deletion and export queues", "queues"],
          ["/contact", "Contact messages", "contact"],
          ["/settings", "Settings", "settings"],
          ["/jobs", "Jobs", "jobs"],
          ["/audit", "Platform audit log", "audit"],
          [
            "/session-required?code=UNAUTHENTICATED",
            "Platform session not started",
            "session-required",
          ],
        ]) {
          await page.goto(`${ADMIN_ORIGIN}${route}`);
          await expect(
            page.getByRole("heading", { level: 1, name: heading, exact: true }),
          ).toBeVisible();
          await shoot(page, `${name}-${suffix}`);
        }
        const headers = await csrfHeaders(page.request);
        const notice = await page.request.post(`${API}/platform/announcements`, {
          headers,
          data: {
            region: "uk",
            title: "Planned service maintenance",
            body: "Reports may take longer while maintenance is in progress.",
            starts_at: new Date(Date.now() - 60_000).toISOString(),
            ends_at: new Date(Date.now() + 3_600_000).toISOString(),
            reason: "Phase 17 screenshot evidence",
          },
        });
        expect(notice.status(), await notice.text()).toBe(201);
        const announcement = await notice.json();
        try {
          await page.goto("/dashboard");
          await expect(page.getByTestId("announcement-banner")).toContainText(
            "Planned service maintenance",
          );
          await shoot(page, `announcement-${suffix}`);
          const list = await page.request.get(`${API}/platform/companies`, {
            params: { q: account.company },
          });
          expect(list.status()).toBe(200);
          const company = (await list.json()).items.find(
            (row: { contact_email: string }) => row.contact_email === account.email,
          );
          expect(company).toBeTruthy();
          const support = await page.request.post(
            `${API}/platform/companies/${company.id}/impersonate`,
            {
              headers: await csrfHeaders(page.request),
              data: { reason: "Phase 17 support screenshot evidence", ticket_ref: "QA-P17" },
            },
          );
          expect(support.status(), await support.text()).toBe(201);
          await page.goto("/dashboard");
          await expect(page.getByTestId("support-banner")).toContainText("Read-only.");
          await shoot(page, `support-${suffix}`);
        } finally {
          const ended = await page.request.post(
            `${API}/platform/announcements/${announcement.id}/end`,
            {
              headers: await csrfHeaders(page.request),
              data: { reason: "Phase 17 screenshots complete" },
            },
          );
          expect(ended.status(), await ended.text()).toBe(200);
        }
      });
    }
  });
}
