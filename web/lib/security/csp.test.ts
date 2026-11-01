import { describe, expect, it } from "vitest";

import {
  GEOLOCATION_PATH_PREFIXES,
  baseSecurityHeaders,
  buildCsp,
  generateNonce,
  originOf,
  permissionsPolicy,
} from "./csp";

function directives(csp: string): Map<string, string[]> {
  return new Map(
    csp.split(";").map((part) => {
      const [name, ...values] = part.trim().split(/\s+/);
      return [name ?? "", values] as const;
    }),
  );
}

const production = { nonce: "TESTNONCE", isDev: false, apiOrigin: "https://api.example.com" };

describe("buildCsp (production)", () => {
  const csp = directives(buildCsp(production));

  it("starts from default-src 'self'", () => {
    expect(csp.get("default-src")).toEqual(["'self'"]);
  });

  it("allows scripts only from self, the nonce, and the Stripe and Turnstile hosts", () => {
    expect(csp.get("script-src")).toEqual([
      "'self'",
      "'nonce-TESTNONCE'",
      "'strict-dynamic'",
      "https://js.stripe.com",
      "https://challenges.cloudflare.com",
    ]);
  });

  it("never allows inline or eval'd scripts", () => {
    const scripts = csp.get("script-src") ?? [];
    expect(scripts).not.toContain("'unsafe-inline'");
    expect(scripts).not.toContain("'unsafe-eval'");
  });

  it("styles use the nonce; only style ATTRIBUTES may be inline", () => {
    expect(csp.get("style-src")).toEqual(["'self'", "'nonce-TESTNONCE'"]);
    expect(csp.get("style-src-attr")).toEqual(["'unsafe-inline'"]);
  });

  it("locks down framing, plugins, base URI and form targets", () => {
    expect(csp.get("frame-ancestors")).toEqual(["'none'"]);
    expect(csp.get("object-src")).toEqual(["'none'"]);
    expect(csp.get("base-uri")).toEqual(["'self'"]);
    expect(csp.get("form-action")).toEqual(["'self'"]);
  });

  it("lets the browser talk to the API and Sentry, and nowhere else", () => {
    expect(csp.get("connect-src")).toEqual([
      "'self'",
      "https://api.example.com",
      "https://*.ingest.sentry.io",
      "https://*.ingest.de.sentry.io",
    ]);
    expect(csp.get("img-src")).toEqual(["'self'", "data:", "blob:", "https://api.example.com"]);
  });

  it("upgrades insecure requests", () => {
    expect(buildCsp(production)).toContain("upgrade-insecure-requests");
  });

  it("omits the API origin when none is configured", () => {
    const without = directives(buildCsp({ nonce: "N", isDev: false }));
    expect(without.get("connect-src")).not.toContain("undefined");
    expect(without.get("img-src")).toEqual(["'self'", "data:", "blob:"]);
  });
});

describe("buildCsp (development)", () => {
  const csp = directives(buildCsp({ nonce: "N", isDev: true }));

  it("adds unsafe-eval for React's debugging, and inline styles for hot reload", () => {
    expect(csp.get("script-src")).toContain("'unsafe-eval'");
    expect(csp.get("style-src")).toContain("'unsafe-inline'");
  });

  it("does not force https", () => {
    expect(buildCsp({ nonce: "N", isDev: true })).not.toContain("upgrade-insecure-requests");
  });
});

describe("generateNonce", () => {
  it("is different every time and is base64", () => {
    const nonces = new Set(Array.from({ length: 200 }, generateNonce));
    expect(nonces.size).toBe(200);
    for (const nonce of nonces) expect(nonce).toMatch(/^[A-Za-z0-9+/]+=*$/);
  });

  it("is long enough to be unguessable", () => {
    expect(generateNonce().length).toBeGreaterThanOrEqual(40);
  });
});

describe("originOf", () => {
  it("reduces a URL to its origin", () => {
    expect(originOf("https://api.example.com/api/v1")).toBe("https://api.example.com");
    expect(originOf("http://localhost:8000/api/v1")).toBe("http://localhost:8000");
  });

  it("ignores missing or malformed values", () => {
    expect(originOf(undefined)).toBeUndefined();
    expect(originOf("")).toBeUndefined();
    expect(originOf("not a url")).toBeUndefined();
  });
});

describe("permissionsPolicy", () => {
  it("denies camera, microphone and geolocation by default", () => {
    expect(permissionsPolicy("/")).toBe("camera=(), microphone=(), geolocation=()");
    expect(permissionsPolicy("/employees")).toBe("camera=(), microphone=(), geolocation=()");
  });

  it("allows geolocation for this origin only on the opt-in clock-in page", () => {
    for (const prefix of GEOLOCATION_PATH_PREFIXES) {
      expect(permissionsPolicy(prefix)).toBe("camera=(), microphone=(), geolocation=(self)");
      expect(permissionsPolicy(`${prefix}/in`)).toContain("geolocation=(self)");
    }
    expect(permissionsPolicy("/clockwork")).toContain("geolocation=()");
  });
});

describe("baseSecurityHeaders", () => {
  it("always sets nosniff, DENY framing and a strict referrer policy", () => {
    for (const production of [true, false]) {
      const headers = baseSecurityHeaders(production);
      expect(headers["X-Content-Type-Options"]).toBe("nosniff");
      expect(headers["X-Frame-Options"]).toBe("DENY");
      expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    }
  });

  it("sets two-year preloaded HSTS in production only", () => {
    expect(baseSecurityHeaders(true)["Strict-Transport-Security"]).toBe(
      "max-age=63072000; includeSubDomains; preload",
    );
    expect(baseSecurityHeaders(false)["Strict-Transport-Security"]).toBeUndefined();
  });
});
