/** T18.1: the public marketing pages open signed out, pass axe in both themes, and the contact form sends. */
import { expect, test, type Page } from "@playwright/test";

import { audit } from "../support/axe";

test.use({ storageState: { cookies: [], origins: [] } });

/** The cookie component reads the stored choice once React has taken over the page. */
const ready = (page: Page) =>
  page
    .locator('[data-consent-state]:not([data-consent-state="loading"])')
    .waitFor({ state: "attached" });

const PAGES = [
  { path: "/", heading: /Look after your people/ },
  { path: "/features", heading: /Everything in one calm place/ },
  { path: "/pricing", heading: /Two plans/ },
  { path: "/security", heading: /Careful with what you trust/ },
  { path: "/about", heading: /Built for employers/ },
  { path: "/contact", heading: /Get in touch/ },
  { path: "/accessibility", heading: /Accessibility statement/ },
  { path: "/careers", heading: /Work at/ },
  { path: "/sponsor-licence-compliance", heading: /Keep your licence in good order/ },
  { path: "/sponsor-licence-compliance/reporting-duties", heading: /Reporting duties/ },
] as const;

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });
    for (const { path, heading } of PAGES) {
      test(`${path} opens and passes axe`, async ({ page }) => {
        await page.goto(path);
        await ready(page);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        await audit(page, `${colorScheme} ${path}`);
      });
    }
  });
}

test("the pricing page shows the prices from config", async ({ page }) => {
  await page.goto("/pricing");
  await expect(page.getByText("£50").first()).toBeVisible();
  await expect(page.getByText("£240").first()).toBeVisible();
  await expect(page.getByText("Best value")).toBeVisible();
});

test("the contact form sends a message", async ({ page }) => {
  await page.goto("/contact");
  await ready(page);
  await page.getByLabel("Name", { exact: true }).fill("Sam Jones");
  await page.getByLabel("Email", { exact: true }).fill("sam@example.com");
  await page.getByLabel("Topic", { exact: true }).selectOption("pricing_billing");
  await page
    .getByLabel("Message", { exact: true })
    .fill("Do you offer a discount for a team of five?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("heading", { name: "Message sent" })).toBeVisible();
});
