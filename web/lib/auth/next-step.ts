import type { components } from "@/lib/api/client";

type LoginResponse = components["schemas"]["LoginResponse"];

/** Where to go once the API has accepted the e-mail address and password (or a link's token). */
export function destinationAfterSignIn(
  response: Pick<LoginResponse, "mfa_required">,
): "/login/mfa" | "/dashboard" {
  return response.mfa_required ? "/login/mfa" : "/dashboard";
}

/** The failed attempts after which the sign-in form asks for the Turnstile check (plan 8.1). */
export const TURNSTILE_AFTER_FAILURES = 3;

export function needsTurnstile(failures: number, lastCode: string | undefined): boolean {
  return failures >= TURNSTILE_AFTER_FAILURES || lastCode === "TURNSTILE_FAILED";
}
