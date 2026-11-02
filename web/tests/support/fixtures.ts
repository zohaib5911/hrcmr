/**
 * `test` for specs that use the signed-in app. Each spec file gets its own company and administrator
 * (a real sign-up, unique names), so no spec depends on what another one left behind or on the
 * database being empty. Import `test` and `expect` from here instead of `@playwright/test`.
 */
import { request, test as base, type BrowserContextOptions } from "@playwright/test";

import { createSignedInAdmin } from "./accounts";

type State = Exclude<BrowserContextOptions["storageState"], string | undefined>;

// One company per spec file per worker. Playwright starts a worker per file when files run in
// parallel, and with one worker the files simply run one after the other.
const sessions = new Map<string, Promise<State>>();

async function signUp(): Promise<State> {
  const api = await request.newContext();
  try {
    await createSignedInAdmin(api);
    return await api.storageState();
  } finally {
    await api.dispose();
  }
}

export const test = base.extend({
  storageState: async ({}, use, testInfo) => {
    let session = sessions.get(testInfo.file);
    if (!session) {
      session = signUp();
      sessions.set(testInfo.file, session);
      // A failed sign-up is not kept: the next test of the file tries again.
      session.catch(() => sessions.delete(testInfo.file));
    }
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Playwright's `use`, not a React hook
    await use(await session);
  },
});

export { expect } from "@playwright/test";
