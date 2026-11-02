import { randomBytes } from "node:crypto";

import { defineConfig } from "@playwright/test";

const WEB_PORT = 3100;
const API_PORT = 8100;
// `next dev` for the /design page, which is a 404 in a production build. Tests address it as
// `localhost`: Next.js blocks the dev server's own resources for any other origin.
const DESIGN_PORT = 3101;
// The specs that need the development server. (design-guard.spec.ts runs against the production build.)
const DESIGN_SPECS = /design(-a11y|-components|-marketing)?\.spec\.ts$/;

const secret = (bytes: number) => randomBytes(bytes).toString("base64url");
const postgresPassword = process.env.POSTGRES_PASSWORD ?? "postgres";
const postgresPort = process.env.POSTGRES_TEST_PORT ?? "5433";
const redisPort = process.env.REDIS_PORT ?? "6379";
// A random key map for this test run only.
const keys = JSON.stringify({ k1: randomBytes(32).toString("base64") });

export default defineConfig({
  testDir: "tests/e2e",
  // Outside web/: `next dev` watches this folder, and a failing test writing its report here made the
  // development server reload every page under test, which timed out the whole "design" project.
  outputDir: "../.playwright-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  projects: [
    {
      name: "production",
      testIgnore: DESIGN_SPECS,
      use: { baseURL: `http://127.0.0.1:${WEB_PORT}` },
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
    // The API, for the typed-client tests. It needs the local Docker stack (`docker compose up -d --wait`).
    // Every secret here is random and used only by this test run.
    {
      command: `uv run --directory ../api uvicorn app.main:create_app --factory --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        APP_ENV: "test",
        DOMAIN: "localhost",
        WEB_ORIGIN: `http://127.0.0.1:${WEB_PORT}`,
        ADMIN_ORIGIN: `http://admin.localhost:${WEB_PORT}`,
        API_ORIGIN: `http://127.0.0.1:${API_PORT}`,
        DATABASE_URL: `postgresql+asyncpg://postgres:${postgresPassword}@127.0.0.1:${postgresPort}/postgres`,
        REDIS_URL: `redis://127.0.0.1:${redisPort}/12`,
        SESSION_SECRET: secret(48),
        FIELD_ENCRYPTION_KEYS: keys,
        BLIND_INDEX_KEY: secret(32),
      },
    },
  ],
});
