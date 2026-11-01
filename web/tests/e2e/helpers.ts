import type { APIResponse } from "@playwright/test";

/** Where the test server listens (see playwright.config.ts). */
export const BASE_URL = "http://127.0.0.1:3100";

/** Host headers as the three kinds of traffic present them. */
export const MAIN_HOST = "example.test";
export const ADMIN_HOST = "admin.example.test";

/** A Content-Security-Policy header split into directive -> values. */
export function parseCsp(header: string | undefined): Map<string, string[]> {
  const result = new Map<string, string[]>();
  for (const part of (header ?? "").split(";")) {
    const [name, ...values] = part.trim().split(/\s+/);
    if (name) result.set(name, values);
  }
  return result;
}

export function nonceOf(csp: Map<string, string[]>): string {
  const token = (csp.get("script-src") ?? []).find((value) => value.startsWith("'nonce-"));
  if (!token) throw new Error("script-src has no nonce");
  return token.slice("'nonce-".length, -1);
}

/** The text of the page's single <h1>, or "" when it has none. */
export async function headingOf(response: APIResponse): Promise<string> {
  const html = await response.text();
  return /<h1[^>]*>([^<]*)<\/h1>/.exec(html)?.[1] ?? "";
}
