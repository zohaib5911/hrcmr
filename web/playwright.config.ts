import { defineConfig } from "@playwright/test";

const WEB_PORT = 3100;
const SESSION_FILE = "../.playwright-results/session.json";
const API_PORT = 8100;
// `next dev` for the /design page, which is a 404 in a production build. Tests address it as
// `localhost`: Next.js blocks the dev server's own resources for any other origin.
const DESIGN_PORT = 3101;
// The specs that need the development server. (design-guard.spec.ts runs against the production build.)
const DESIGN_SPECS = /design(-a11y|-components|-marketing)?\.spec\.ts$/;

const postgresPassword = process.env.POSTGRES_PASSWORD ?? "postgres";
const postgresPort = process.env.POSTGRES_TEST_PORT ?? "5433";
const redisPort = process.env.REDIS_PORT ?? "6379";

export default defineConfig({
  testDir: "tests/e2e",
  // Outside web/: `next dev` watches this folder, and a failing test writing its report here made the
  // development server reload every page under test, which timed out the whole "design" project.
  outputDir: "../.playwright-results",
  fullyParallel: true,
  // One worker locally: every spec file signs up its own company (tests/support/fixtures.ts), and the
  // one throwaway database and Mailpit inbox stay easy to follow. CI uses Playwright's default.
  workers: process.env.CI ? undefined : Number(process.env.E2E_WORKERS ?? 1),
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  projects: [
    // Makes an account and signs in once; the production tests below start from that session.
    {
      name: "setup",
      testMatch: /auth\.setup\.ts$/,
      use: { baseURL: `http://127.0.0.1:${WEB_PORT}` },
    },
    {
      name: "production",
      testIgnore: DESIGN_SPECS,
      dependencies: ["setup"],
      use: {
        baseURL: `http://127.0.0.1:${WEB_PORT}`,
        storageState: SESSION_FILE,
        // The admin host (T17.1) is a name the browser resolves to the local web server, so a page can
        // open http://admin.example.test:3100/ (C3.1.3). Only that name is mapped.
        launchOptions: { args: ["--host-resolver-rules=MAP admin.example.test 127.0.0.1"] },
      },
    },
    {
      name: "design",
      testMatch: DESIGN_SPECS,
      use: { baseURL: `http://localhost:${DESIGN_PORT}`, browserName: "chromium" },
    },
  ],
  webServer: [
    // The web app: the PRODUCTION build served the way the Docker image serves it, because that is
    // what the security headers and the host routing have to be right for.
    {
      command: "pnpm build && pnpm start",
      url: `http://127.0.0.1:${WEB_PORT}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      // The pages that call the API (sign-in) are built to call the test API below.
      env: { PORT: String(WEB_PORT), NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}/api/v1` },
    },
    // The development server, for tests/e2e/design.spec.ts only. It writes to .next/dev, so it does
    // not disturb the production build above.
    {
      command: `pnpm exec next dev --port ${DESIGN_PORT} --hostname 0.0.0.0`,
      url: `http://127.0.0.1:${DESIGN_PORT}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_TELEMETRY_DISABLED: "1" },
    },
    // The API, with a throwaway database and e-mail straight into Mailpit (api/tests/e2e_server.py).
    // It needs the local Docker stack: `docker compose up -d --wait postgres-test redis mailpit`.
    {
      command: "uv run --directory ../api python -m tests.e2e_server",
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      // Never reused: each run starts the API on a brand-new throwaway database (and flushed Redis),
      // so nothing from an earlier run can change what a test sees.
      reuseExistingServer: false,
      timeout: 90_000,
      env: {
        E2E_API_PORT: String(API_PORT),
        E2E_WEB_ORIGIN: `http://127.0.0.1:${WEB_PORT}`,
        E2E_REDIS_URL: `redis://127.0.0.1:${redisPort}/12`,
        POSTGRES_PASSWORD: postgresPassword,
        POSTGRES_TEST_PORT: postgresPort,
      },
    },
  ],
});
