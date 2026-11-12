import { defineConfig } from "@playwright/test";

/** Public SEO needs only the production web server; no account or API fixture is required. */
export default defineConfig({
  testDir: "tests/e2e",
  testMatch: "marketing-seo.spec.ts",
  outputDir: "../.playwright-results/seo",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3100" },
  webServer: {
    command: "pnpm start",
    url: "http://127.0.0.1:3100/healthz",
    reuseExistingServer: false,
    env: { PORT: "3100", HOSTNAME: "0.0.0.0" },
  },
});
