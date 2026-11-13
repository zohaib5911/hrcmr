// @vitest-environment jsdom
import * as Sentry from "@sentry/browser";
import { describe, expect, it } from "vitest";

import { beforeSend, privacyOptions } from "./telemetry";

describe("telemetry privacy", () => {
  it("drops every unrestricted carrier including exception text and source context", () => {
    const event: Sentry.ErrorEvent = {
      type: undefined,
      event_id: "abc",
      level: "error",
      user: { email: "PRIVATE-USER" },
      request: { data: "PRIVATE-BODY", headers: { Authorization: "PRIVATE-AUTH" } },
      extra: { salary: "PRIVATE-SALARY" },
      tags: { note: "PRIVATE-TAG" },
      breadcrumbs: [{ message: "PRIVATE-BREADCRUMB" }],
      message: "PRIVATE-MESSAGE",
      exception: {
        values: [
          {
            type: "TypeError",
            value: "PRIVATE-ERROR",
            stacktrace: {
              frames: [
                {
                  function: "render",
                  filename: "PRIVATE-FILE",
                  context_line: "PRIVATE-CODE",
                  vars: { user: "PRIVATE-LOCAL" },
                  lineno: 7,
                },
              ],
            },
          },
        ],
      },
    };
    const clean = beforeSend(event);
    expect(JSON.stringify(clean)).not.toContain("PRIVATE");
    expect(clean.exception?.values?.[0]).toEqual({
      type: "TypeError",
      value: "[redacted]",
      stacktrace: { frames: [{ function: "render", lineno: 7 }] },
    });
    expect(event.request?.data).toBe("PRIVATE-BODY");
  });

  it("scrubs the event produced by the real browser SDK", async () => {
    const events: unknown[] = [];
    const client = new Sentry.BrowserClient({
      dsn: "https://public@example.test/1",
      ...privacyOptions,
      integrations: [],
      stackParser: Sentry.defaultStackParser,
      transport: () => ({
        send: async (envelope) => {
          for (const [header, body] of envelope[1]) {
            if (header.type === "event") events.push(body);
          }
          return {};
        },
        flush: async () => true,
      }),
    });
    const scope = new Sentry.Scope();
    scope.setClient(client);
    scope.setUser({ email: "PRIVATE-USER" });
    scope.setExtra("body", "PRIVATE-BODY");
    scope.captureException(new Error("PRIVATE-ERROR"));
    await client.flush();
    expect(events).toHaveLength(1);
    expect(JSON.stringify(events)).not.toContain("PRIVATE");
    await client.close();
  });
});
