import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { createApiClient } from "../../lib/api/client";

/**
 * A REAL call from the generated TypeScript client to a running FastAPI server (started by
 * playwright.config.ts). If the API changes shape and web/lib/api/schema.ts is not regenerated,
 * `tsc` fails; if it is regenerated but the behaviour differs, these assertions fail.
 */
const api = createApiClient({ baseUrl: "http://127.0.0.1:8100/api/v1", readCookies: () => "" });

test("GET /health returns the typed liveness body", async () => {
  const { data, error, response } = await api.GET("/health");
  expect(error).toBeUndefined();
  expect(response.status).toBe(200);
  expect(data).toEqual({ status: "ok" });
  expect(response.headers.get("x-request-id")).toMatch(/^[0-9a-f]{32}$/);
  expect(response.headers.get("cache-control")).toBe("no-store");
});

test("GET /ready reports the database and Redis", async () => {
  const { data, error } = await api.GET("/ready");
  expect(error).toBeUndefined();
  expect(data).toEqual({ status: "ready", checks: { database: "ok", redis: "ok" } });
});

test("a failing call comes back as the documented error envelope", async () => {
  // Not part of the typed surface on purpose: the typed client cannot call a path that does not exist.
  const response = await fetch("http://127.0.0.1:8100/api/v1/does-not-exist");
  expect(response.status).toBe(404);
  const body = (await response.json()) as {
    error: { code: string; message: string; request_id: string };
  };
  expect(body.error.code).toBe("NOT_FOUND");
  expect(body.error.request_id).toBe(response.headers.get("x-request-id"));
});

test("the API serves the same contract the types were generated from", async () => {
  const served = (await (await fetch("http://127.0.0.1:8100/api/v1/openapi.json")).json()) as {
    servers: { url: string }[];
    paths: Record<string, unknown>;
  };
  expect(served.servers).toEqual([{ url: "/api/v1" }]);
  // The paths the generated file declares, read from its text: `paths` is a type, gone at run time.
  const generated = [
    ...readFileSync("lib/api/schema.ts", "utf8").matchAll(/^ {4}"(\/[^"]*)": \{$/gm),
  ].map((match) => match[1]);
  expect(generated).toContain("/health");
  expect(Object.keys(served.paths).sort()).toEqual([...generated].sort());
});
