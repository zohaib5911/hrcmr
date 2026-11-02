import { describe, expect, it, vi } from "vitest";

import { PLAN_REQUIRED_EVENT, planRequired } from "./request";

const run = (response: Response, target: { dispatchEvent: (event: Event) => boolean }) =>
  (planRequired(target).onResponse as (o: { response: Response }) => Promise<unknown>)({
    response,
  });
const refuse = (status: number, code: string) =>
  new Response(
    JSON.stringify({ error: { code, message: "Subscribe to add employees.", request_id: "r" } }),
    {
      status,
    },
  );

describe("planRequired", () => {
  it("announces a 402 PLAN_REQUIRED with the API's own words, and nothing else", async () => {
    const dispatchEvent = vi.fn(() => true);
    await run(refuse(402, "PLAN_REQUIRED"), { dispatchEvent });
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    const event = (dispatchEvent.mock.calls[0] as unknown as [CustomEvent])[0];
    expect(event.type).toBe(PLAN_REQUIRED_EVENT);
    expect(event.detail).toEqual({ message: "Subscribe to add employees." });

    dispatchEvent.mockClear();
    await run(refuse(402, "SOMETHING_ELSE"), { dispatchEvent });
    await run(refuse(403, "PLAN_REQUIRED"), { dispatchEvent });
    await run(new Response("no body", { status: 402 }), { dispatchEvent });
    expect(dispatchEvent).not.toHaveBeenCalled();
  });
});

describe("ensureCsrfCookie", () => {
  it("makes a first request only when the browser has no CSRF cookie yet", async () => {
    const { ensureCsrfCookie } = await import("./request");
    const get = vi.fn(async () => new Response("{}"));
    await ensureCsrfCookie(
      () => "https://api.test/api/v1",
      () => "csrf=abc; other=1",
      get,
    );
    expect(get).not.toHaveBeenCalled();
    await ensureCsrfCookie(
      () => "https://api.test/api/v1",
      () => "other=1",
      get,
    );
    expect(get).toHaveBeenCalledWith("https://api.test/api/v1/health", { credentials: "include" });
  });
});
