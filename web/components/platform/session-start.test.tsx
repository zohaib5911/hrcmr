// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionStart, startFromBrowser, type StartResult } from "./session-start";

describe("SessionStart", () => {
  it("says it is starting, then goes on to the page the person asked for", async () => {
    const navigate = vi.fn();
    const run = vi.fn(async (): Promise<StartResult> => ({ ok: true }));
    render(<SessionStart next="/rules" run={run} navigate={navigate} />);
    expect(screen.getByRole("status")).toHaveTextContent("Starting a platform session");
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/rules"));
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("sends a refusal to the refusal page with its code", async () => {
    const navigate = vi.fn();
    const run = async (): Promise<StartResult> => ({ ok: false, code: "MFA_REQUIRED" });
    render(<SessionStart next="/rules" run={run} navigate={navigate} />);
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("/session-required?code=MFA_REQUIRED"),
    );
  });

  it("goes to the home page when the next path is not safe", async () => {
    const navigate = vi.fn();
    const run = async (): Promise<StartResult> => ({ ok: true });
    render(<SessionStart next="//evil.example" run={run} navigate={navigate} />);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
  });
});

describe("startFromBrowser", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    document.cookie = "csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("posts to the configured API origin with credentials and the CSRF header", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.configured.test/api/v1");
    document.cookie = "csrf=abc";
    const seen: Request[] = [];
    const fetchMock = vi.fn(async (req: Request) => {
      seen.push(req);
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal("fetch", fetchMock);
    expect(await startFromBrowser()).toEqual({ ok: true });
    const req = seen[0]!;
    expect(req.url).toBe("https://api.configured.test/api/v1/auth/platform-session");
    expect(req.method).toBe("POST");
    expect(req.credentials).toBe("include");
    expect(req.headers.get("X-CSRF-Token")).toBe("abc");
  });

  it("returns the API's refusal code", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.configured.test/api/v1");
    document.cookie = "csrf=abc";
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: "MFA_REQUIRED" } }), {
            status: 403,
            headers: { "content-type": "application/json" },
          }),
      ),
    );
    expect(await startFromBrowser()).toEqual({ ok: false, code: "MFA_REQUIRED" });
  });
});
