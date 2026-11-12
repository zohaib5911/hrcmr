/**
 * Takes the product screenshots shown on the public Features page (plan 5.9, T18.1): the signed-in
 * app with a few demo people, in light and dark, at 1280 x 800, into web/public/marketing/.
 * Run only when asked, then commit the images:
 *
 *   SCREENSHOTS=1 pnpm exec playwright test marketing-screenshots --project=production
 */
import path from "node:path";

import { test } from "@playwright/test";

import { API, csrfHeaders } from "../support/accounts";
import { settled } from "../support/settle";

const OUT = path.resolve(__dirname, "../../public/marketing");

test.skip(!process.env.SCREENSHOTS, "Screenshots are only taken on request (SCREENSHOTS=1).");

const SHOTS = [
  { name: "people", path: "/employees" },
  { name: "compliance", path: "/sponsor-compliance" },
  { name: "leave", path: "/leave" },
  { name: "attendance", path: "/attendance" },
  { name: "rota", path: "/rota" },
  { name: "documents", path: "/documents" },
  { name: "learning", path: "/learning" },
  { name: "recruitment", path: "/recruitment" },
] as const;

const DEMO_PEOPLE = [
  ["Amara", "Okafor"],
  ["Daniel", "Whitaker"],
  ["Priya", "Nair"],
  ["Tomasz", "Kowalski"],
  ["Hannah", "Reilly"],
  ["Leo", "Marchetti"],
] as const;

test.beforeAll(async ({ request }) => {
  const headers = await csrfHeaders(request);
  for (const [index, [first, last]] of DEMO_PEOPLE.entries()) {
    await request.post(`${API}/employees`, {
      headers,
      data: {
        first_name: first,
        last_name: last,
        email: `${first}.${last}@example.com`.toLowerCase(),
        employee_number: `D${index + 1}`,
        hire_date: "2025-03-03",
      },
    });
  }
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(colorScheme, () => {
    test.use({ colorScheme, viewport: { width: 1280, height: 800 } });
    for (const shot of SHOTS) {
      test(`${shot.name}`, async ({ page }) => {
        await page.goto(shot.path);
        await page
          .locator('[data-consent-state]:not([data-consent-state="loading"])')
          .waitFor({ state: "attached" });
        await settled(page);
        await page.screenshot({ path: path.join(OUT, `${shot.name}-${colorScheme}.png`) });
      });
    }
  });
}
