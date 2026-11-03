/** Phase 8 gate evidence: 390/1280 px, light/dark. */
import path from "node:path";
import type { Page } from "@playwright/test";
import { API, csrfHeaders } from "../support/accounts";
import { expect, test } from "../support/fixtures";
import { audit } from "../support/axe";

const OUT = path.resolve(__dirname, "../../../docs/screenshots/phase-8");
test.skip(!process.env.SCREENSHOTS, "Phase gate screenshots only.");

async function shoot(page: Page, name: string, modal = false) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  await page.mouse.move(0, 0);
  await audit(page, name, { modal });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
  await page.screenshot({
    path: path.join(OUT, name + ".png"),
    fullPage: !modal,
    animations: "disabled",
  });
}

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme });
    for (const width of [390, 1280]) {
      test(`Leave at ${width}px`, async ({ page, context }) => {
        test.setTimeout(120_000);
        await page.setViewportSize({ width, height: 900 });
        const suffix = `${colorScheme}-${width}`;
        const headers = await csrfHeaders(context.request);
        const api = context.request;
        expect(
          (
            await api.put(`${API}/working-pattern`, {
              headers,
              data: {
                days: Array.from({ length: 7 }, (_, i) => ({
                  weekday: i + 1,
                  is_working: i < 5,
                  hours: i < 5 ? "8" : "0",
                })),
                bank_holidays_non_working: false,
              },
            })
          ).status(),
        ).toBe(200);
        const people: string[] = [];
        for (const [i, name] of ["Mira", "Amina"].entries()) {
          const made = await api.post(`${API}/employees`, {
            headers,
            data: {
              first_name: name,
              last_name: "Patel",
              email: `${name.toLowerCase()}@example.com`,
              employee_number: `${suffix}-${i}`,
              hire_date: "2025-01-06",
            },
          });
          expect(made.status(), await made.text()).toBe(201);
          people.push((await made.json()).id);
        }
        const kinds = (await (await api.get(`${API}/leave/types`)).json()) as {
          id: string;
          seed_key: string;
        }[];
        const annual = kinds.find((t) => t.seed_key === "annual")!.id;
        for (const start of ["2026-11-09", "2026-11-12"]) {
          const made = await api.post(`${API}/leave/requests`, {
            headers,
            data: {
              employee_id: people[0],
              leave_type_id: annual,
              start_date: start,
              end_date: start,
            },
          });
          expect(made.status(), await made.text()).toBe(201);
          if (start === "2026-11-09")
            expect(
              (
                await api.post(`${API}/leave/requests/${(await made.json()).id}/approve`, {
                  headers,
                  data: { note: "Coverage reviewed" },
                })
              ).status(),
            ).toBe(200);
        }
        const users = (await (await api.get(`${API}/users`)).json()).users as {
          id: string;
          is_you: boolean;
        }[];
        expect(
          (
            await api.put(`${API}/users/${users.find((u) => u.is_you)!.id}/employee`, {
              headers,
              data: { employee_id: people[1] },
            })
          ).status(),
        ).toBe(200);
        await page.goto("/leave");
        await expect(
          page.getByRole("heading", { level: 1, name: "Leave", exact: true }),
        ).toBeVisible();
        await page.getByLabel("Month", { exact: true }).fill("2026-11");
        await expect(
          page.getByRole("button", { name: /Monday 9 November 2026, [1-9]/ }),
        ).toBeVisible();
        await shoot(page, `calendar-${suffix}`);
        await page.getByRole("radio", { name: "Requests", exact: true }).click();
        await expect(
          page.getByRole("button", { name: "Review request", exact: true }).first(),
        ).toBeVisible();
        await shoot(page, `requests-${suffix}`);
        await page.getByRole("button", { name: "Review request", exact: true }).first().click();
        const review = page.getByRole("dialog", { name: "Review leave request", exact: true });
        await expect(review.getByRole("button", { name: "Approve", exact: true })).toBeEnabled();
        await shoot(page, `decision-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.getByRole("radio", { name: "Balances", exact: true }).click();
        await expect(
          page.getByRole("button", { name: "Adjust Annual Leave", exact: true }).first(),
        ).toBeVisible();
        await shoot(page, `balances-${suffix}`);
        await page.goto(`/employees/${people[0]}?tab=leave`);
        await expect(
          page.getByRole("button", { name: "Adjust Annual Leave", exact: true }),
        ).toBeVisible();
        await shoot(page, `employee-leave-${suffix}`);
        await page.getByRole("button", { name: "Adjust Annual Leave", exact: true }).click();
        await expect(
          page.getByRole("dialog", { name: "Adjust Annual Leave", exact: true }),
        ).toBeVisible();
        await shoot(page, `balance-action-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.goto("/my-leave");
        await expect(
          page.getByRole("button", { name: "Request leave", exact: true }),
        ).toBeVisible();
        await expect(page.getByText("12 rows", { exact: true })).toBeVisible();
        await shoot(page, `my-leave-${suffix}`);
        await page.getByRole("button", { name: "Request leave", exact: true }).click();
        const request = page.getByRole("dialog", { name: "Request leave", exact: true });
        await request.getByLabel("Start date", { exact: true }).fill("2026-11-16");
        await request.getByLabel("End date", { exact: true }).fill("2026-11-17");
        await expect(request.getByRole("status")).toHaveText("2 working days");
        await shoot(page, `request-form-${suffix}`, true);
        await page.keyboard.press("Escape");
        await page.goto("/my-approvals");
        await expect(
          page.getByRole("button", { name: "Review request", exact: true }).first(),
        ).toBeVisible();
        await shoot(page, `my-approvals-${suffix}`);
        await page.goto("/leave/settings");
        await expect(page.getByText("12 rows", { exact: true })).toBeVisible();
        await shoot(page, `settings-${suffix}`);
        await page.getByRole("link", { name: "Year end", exact: true }).click();
        await page.getByLabel("Leave year starts", { exact: true }).fill("2025-01-01");
        await page.getByRole("button", { name: "Preview year", exact: true }).click();
        await expect(
          page.getByRole("button", { name: "Commit year end", exact: true }),
        ).toBeVisible();
        await shoot(page, `year-end-${suffix}`);
        await page
          .getByRole("button", { name: "Override Annual Leave", exact: true })
          .first()
          .click();
        await expect(
          page.getByRole("dialog", { name: "Override Annual Leave", exact: true }),
        ).toBeVisible();
        await shoot(page, `carry-override-${suffix}`, true);
      });
    }
  });
}
