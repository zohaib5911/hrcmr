import { describe, expect, expectTypeOf, it } from "vitest";

import {
  browserApiBaseUrl,
  createApiClient,
  csrfMiddleware,
  readCookie,
  serverApiBaseUrl,
  type ApiErrorEnvelope,
} from "./client";
import type { components } from "./schema";

type Health = components["schemas"]["HealthResponse"];
type Ready = components["schemas"]["ReadyResponse"];

/** A `fetch` that records what it was asked for and answers with a canned JSON body. */
function fakeFetch(status: number, body: unknown, seen: Request[] = []): typeof fetch {
  return async (input, init) => {
    seen.push(input instanceof Request ? input : new Request(input, init));
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  };
}

const BASE = "http://api.test/api/v1";

describe("a typed GET /health", () => {
  it("returns data typed as the API's HealthResponse", async () => {
    const seen: Request[] = [];
    const api = createApiClient({
      baseUrl: BASE,
      fetch: fakeFetch(200, { status: "ok" }, seen),
      readCookies: () => "",
    });

    const { data, error, response } = await api.GET("/health");

    expect(data).toEqual({ status: "ok" });
    expect(error).toBeUndefined();
    expect(response.status).toBe(200);
    expectTypeOf(data).toEqualTypeOf<Health | undefined>();
    expectTypeOf(data?.status).toEqualTypeOf<"ok" | undefined>();
    expectTypeOf(error).toEqualTypeOf<ApiErrorEnvelope | undefined>();
    // The documented path is relative to the server, so the base URL's /api/v1 is not repeated.
    expect(seen[0]?.url).toBe("http://api.test/api/v1/health");
  });

  it("sends the session cookie (credentials: include)", async () => {
    const seen: Request[] = [];
    const api = createApiClient({
      baseUrl: BASE,
      fetch: fakeFetch(200, { status: "ok" }, seen),
      readCookies: () => "",
    });
    await api.GET("/health");
    expect(seen[0]?.credentials).toBe("include");
  });

  it("types the error as the envelope the API really returns", async () => {
    const body: ApiErrorEnvelope = {
      error: { code: "INTERNAL_ERROR", message: "Something went wrong.", request_id: "req-1" },
    };
    const api = createApiClient({
      baseUrl: BASE,
      fetch: fakeFetch(500, body),
      readCookies: () => "",
    });

    const { data, error } = await api.GET("/health");

    expect(data).toBeUndefined();
    expect(error?.error.code).toBe("INTERNAL_ERROR");
    expect(error?.error.request_id).toBe("req-1");
    expectTypeOf(error?.error.code).toEqualTypeOf<string | undefined>();
    expectTypeOf(error?.error.field).toEqualTypeOf<string | null | undefined>();
  });
});

describe("a typed GET /ready", () => {
  it("returns the checks when ready", async () => {
    const body: Ready = { status: "ready", checks: { database: "ok", redis: "ok" } };
    const api = createApiClient({
      baseUrl: BASE,
      fetch: fakeFetch(200, body),
      readCookies: () => "",
    });
    const { data } = await api.GET("/ready");
    expectTypeOf(data).toEqualTypeOf<Ready | undefined>();
    expect(data?.checks.database).toBe("ok");
  });

  it("a 503 is documented, so its body is typed too", async () => {
    const body: Ready = { status: "not_ready", checks: { database: "fail", redis: "ok" } };
    const api = createApiClient({
      baseUrl: BASE,
      fetch: fakeFetch(503, body),
      readCookies: () => "",
    });

    const { data, error } = await api.GET("/ready");

    expect(data).toBeUndefined();
    expectTypeOf(error).toEqualTypeOf<Ready | ApiErrorEnvelope | undefined>();
    expect(error && "checks" in error ? error.checks.database : undefined).toBe("fail");
  });
});

describe("the generated types are the contract", () => {
  it("only the paths the API documents can be called", () => {
    type Api = ReturnType<typeof createApiClient>;
    expectTypeOf<Parameters<Api["GET"]>[0]>().toEqualTypeOf<"/health" | "/ready">();
  });

  it("the error body has the documented required fields", () => {
    expectTypeOf<components["schemas"]["ErrorBody"]>().toEqualTypeOf<{
      code: string;
      message: string;
      field?: string | null;
      request_id: string;
    }>();
  });
});

describe("headers", () => {
  it("forwards headers given for server-side rendering, such as the caller's cookie", async () => {
    const seen: Request[] = [];
    const api = createApiClient({
      baseUrl: BASE,
      fetch: fakeFetch(200, { status: "ok" }, seen),
      readCookies: () => "",
      headers: { cookie: "brand_session=abc", "x-request-id": "trace-12345678" },
    });
    await api.GET("/health");
    expect(seen[0]?.headers.get("cookie")).toBe("brand_session=abc");
    expect(seen[0]?.headers.get("x-request-id")).toBe("trace-12345678");
  });
});

describe("readCookie", () => {
  it.each([
    ["csrf=abc", "abc"],
    ["a=1; csrf=abc; b=2", "abc"],
    ["csrf=a%3Db%3D", "a=b="],
    ["csrf=a=b", "a=b"],
    ["  csrf=abc  ", "abc"],
  ])("%j -> %j", (cookies, expected) => {
    expect(readCookie("csrf", cookies)).toBe(expected);
  });

  it("returns undefined when absent", () => {
    expect(readCookie("csrf", "")).toBeUndefined();
    expect(readCookie("csrf", "xcsrf=1; csrfx=2")).toBeUndefined();
  });
});

describe("csrfMiddleware", () => {
  const run = (method: string, cookies: string) => {
    const request = new Request("http://api.test/api/v1/x", { method });
    const result = csrfMiddleware(() => cookies).onRequest?.({ request } as never);
    return (result instanceof Request ? result : request).headers.get("X-CSRF-Token");
  };

  it.each(["POST", "PUT", "PATCH", "DELETE", "post"])("adds the token on %s", (method) => {
    expect(run(method, "csrf=tok123")).toBe("tok123");
  });

  it.each(["GET", "HEAD", "OPTIONS"])("does not add it on %s", (method) => {
    expect(run(method, "csrf=tok123")).toBeNull();
  });

  it("adds nothing when there is no csrf cookie", () => {
    expect(run("POST", "other=1")).toBeNull();
  });
});

describe("base URLs", () => {
  it("uses NEXT_PUBLIC_API_URL when set", () => {
    expect(browserApiBaseUrl({ NEXT_PUBLIC_API_URL: "https://api.example.com/api/v1" })).toBe(
      "https://api.example.com/api/v1",
    );
  });

  it("falls back to localhost only outside production", () => {
    expect(browserApiBaseUrl({ NODE_ENV: "development" })).toBe("http://localhost:8000/api/v1");
    expect(() => browserApiBaseUrl({ NODE_ENV: "production" })).toThrow("NEXT_PUBLIC_API_URL");
  });

  it("server rendering prefers the private network address", () => {
    const env = {
      API_INTERNAL_URL: "http://api.railway.internal:8000/api/v1",
      NEXT_PUBLIC_API_URL: "https://api.example.com/api/v1",
    };
    expect(serverApiBaseUrl(env)).toBe("http://api.railway.internal:8000/api/v1");
    expect(serverApiBaseUrl({ NEXT_PUBLIC_API_URL: "https://api.example.com/api/v1" })).toBe(
      "https://api.example.com/api/v1",
    );
  });
});
