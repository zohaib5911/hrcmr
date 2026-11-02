/**
 * Making a real account for a browser test, the way a person does: sign up, then open the link in the
 * e-mail (read from Mailpit). The API under test is `api/tests/e2e_server.py`.
 */
import { expect, type APIRequestContext } from "@playwright/test";

export const API = "http://127.0.0.1:8100/api/v1";
export const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";

export interface Account {
  email: string;
  password: string;
  company: string;
}

export function newAccount(label = "admin"): Account {
  const stamp = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  return {
    email: `${label}-${stamp}@example.com`,
    // Long, unusual and not in any breach list.
    password: `violet teapot ${stamp} ledger orchard`,
    company: `Harbourside Care ${stamp}`,
  };
}

/** The CSRF header every state-changing request carries (the cookie is issued on the first request). */
export async function csrfHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  await request.get(`${API}/health`);
  const { cookies } = await request.storageState();
  const token = cookies.find((cookie) => cookie.name === "csrf")?.value;
  expect(token, "the API issues a csrf cookie").toBeTruthy();
  return { "X-CSRF-Token": token ?? "" };
}

/** The newest message to `email` whose subject starts with `subject`, as plain text. */
export async function waitForMail(
  request: APIRequestContext,
  email: string,
  subject: string,
): Promise<string> {
  let text = "";
  await expect
    .poll(
      async () => {
        const found = await request.get(`${MAILPIT}/api/v1/search`, {
          params: { query: `to:${email} subject:"${subject}"` },
        });
        const { messages } = (await found.json()) as { messages: { ID: string }[] };
        if (messages.length === 0) return false;
        const message = await request.get(`${MAILPIT}/api/v1/message/${messages[0]?.ID}`);
        text = ((await message.json()) as { Text: string }).Text;
        return true;
      },
      { message: `waiting for "${subject}" to reach ${email}`, timeout: 15_000 },
    )
    .toBe(true);
  return text;
}

/** The one-time token in the first link of a message that points at `path`. */
export function tokenIn(text: string, path: string): string {
  const match = new RegExp(`${path}\\?token=([\\w-]+)`).exec(text);
  expect(match, `a ${path} link in the e-mail`).not.toBeNull();
  return match?.[1] ?? "";
}

/** Signs up, confirms the address from the e-mail, and leaves the session in `request`. */
export async function createSignedInAdmin(
  request: APIRequestContext,
  account: Account = newAccount(),
): Promise<Account> {
  const headers = await csrfHeaders(request);
  // The test API trusts X-Real-IP from this machine (api/tests/e2e_server.py), so a sign-up made here
  // counts against a made-up address and not the shared one that allows only 5 an hour.
  const visitor = `10.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${1 + Math.floor(Math.random() * 254)}`;
  const signup = await request.post(`${API}/auth/signup`, {
    headers: { ...headers, "X-Real-IP": visitor },
    data: {
      company_name: account.company,
      bank_holiday_region: "england-and-wales",
      first_name: "Amira",
      last_name: "Hassan",
      email: account.email,
      password: account.password,
      accept_terms: true,
    },
  });
  expect(signup.status(), await signup.text()).toBe(202);
  const mail = await waitForMail(request, account.email, "Confirm your email address");
  const verified = await request.post(`${API}/auth/verify-email`, {
    headers,
    data: { token: tokenIn(mail, "/verify-email") },
  });
  expect(verified.status(), await verified.text()).toBe(200);
  return account;
}
