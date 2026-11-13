import { expect, type Locator } from "@playwright/test";

import { brand } from "@brand";

/** Check the file actually decoded, as well as the theme's visible accessible artwork. */
export async function expectBrandLogo(scope: Locator, theme: "light" | "dark") {
  const logo = scope.getByRole("img", { name: brand.name, exact: true });
  await expect(logo).toBeVisible();
  await expect(logo).toHaveAttribute(
    "src",
    theme === "light" ? brand.logo.fullLockup : brand.logo.fullLockupDark,
  );
  await expect(logo).toHaveJSProperty("complete", true);
  expect(await logo.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(
    0,
  );
}
