import { clearApiCache } from "@/lib/api/cache";

import { attempt, type Outcome } from "./request";

export const SIGN_OUT_FAILED =
  "We could not confirm you are signed out. Check your connection and try again.";

/**
 * Signs out (ISS-03). It succeeds only when the server revoked the session, or says there is no
 * session any more. Cached answers are cleared either way, so no record stays on screen; on any
 * other outcome the caller reports the failure and offers to try again.
 */
export async function signOut(): Promise<Outcome<null>> {
  const outcome = await attempt((client) => client.POST("/auth/logout"));
  clearApiCache();
  if (outcome.ok || outcome.problem.code === "UNAUTHENTICATED") return { ok: true, data: null };
  return { ok: false, problem: { ...outcome.problem, message: SIGN_OUT_FAILED } };
}
