/**
 * Runs once before the browser tests of the production build: makes a company and its administrator
 * (a real sign-up and e-mail confirmation) and saves the signed-in browser state, so the tests of the
 * signed-in app start signed in. Tests of the sign-in screens themselves start signed out.
 */
import { test as setup } from "@playwright/test";

import { createSignedInAdmin } from "../support/accounts";

// The same path as `SESSION_FILE` in playwright.config.ts, which the other tests start from.
const SESSION_FILE = "../.playwright-results/session.json";

setup("a company administrator is signed in", async ({ request }) => {
  await createSignedInAdmin(request);
  await request.storageState({ path: SESSION_FILE });
});
