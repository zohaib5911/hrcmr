import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Outcome } from "./request";

const attempt = vi.fn<(run: unknown) => Promise<Outcome<unknown>>>();
vi.mock("./request", () => ({ attempt: (run: unknown) => attempt(run) }));

import { cached, clearApiCache, remember } from "@/lib/api/cache";
import { SIGN_OUT_FAILED, signOut } from "./sign-out";

describe("signOut (ISS-03)", () => {
  beforeEach(() => {
    attempt.mockReset();
    clearApiCache();
  });

  it("succeeds when the server revoked the session, or there was none", async () => {
    attempt.mockResolvedValueOnce({ ok: true, data: undefined });
    expect((await signOut()).ok).toBe(true);
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: { code: "UNAUTHENTICATED", message: "Sign in to continue." },
    });
    expect((await signOut()).ok).toBe(true);
  });

  it("reports a failure when the server was not reached, and clears cached records anyway", async () => {
    remember("/employees", { items: ["someone"] });
    attempt.mockResolvedValueOnce({
      ok: false,
      problem: { code: "NETWORK", message: "We could not reach the server." },
    });
    const outcome = await signOut();
    expect(outcome).toEqual({
      ok: false,
      problem: { code: "NETWORK", message: SIGN_OUT_FAILED },
    });
    expect(cached("/employees")).toBeUndefined();

    attempt.mockResolvedValueOnce({ ok: true, data: undefined }); // the retry revokes it
    expect((await signOut()).ok).toBe(true);
  });
});
