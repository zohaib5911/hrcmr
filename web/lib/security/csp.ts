/**
 * Content-Security-Policy and the other response security headers (plan.md section 4.6).
 *
 * A fresh nonce is generated for every request by the proxy. Next.js reads it from the CSP header
 * and puts it on its own scripts and styles, so pages that use it must be rendered per request
 * (the root layout opts in with `connection()`).
 *
 * Pure functions: no Next.js imports, so they are unit-tested directly.
 */

export interface CspOptions {
  nonce: string;
  /** `next dev` needs `unsafe-eval` (React debugging) and inline styles (hot reload). */
  isDev: boolean;
  /** Origin of the API, which the browser calls with fetch. Example: https://api.example.com */
  apiOrigin?: string | undefined;
}

const STRIPE = ["https://js.stripe.com"];
const STRIPE_FRAMES = ["https://js.stripe.com", "https://hooks.stripe.com"];
const TURNSTILE = ["https://challenges.cloudflare.com"];
// Sentry browser SDK reports (EU and US ingest hosts).
const SENTRY = [
  "https://*.ingest.sentry.io",
  "https://*.ingest.us.sentry.io",
  "https://*.ingest.de.sentry.io",
];

export function originOf(url: string | undefined): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(url).origin;
  } catch {
    return undefined;
  }
}

export function buildCsp({ nonce, isDev, apiOrigin }: CspOptions): string {
  const api = apiOrigin ? [apiOrigin] : [];
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // 'strict-dynamic' lets the nonce'd scripts load their own dependencies (Stripe, Turnstile);
    // browsers that ignore it fall back to the explicit hosts.
    "script-src": [
      "'self'",
      `'nonce-${nonce}'`,
      "'strict-dynamic'",
      ...STRIPE,
      ...TURNSTILE,
      ...(isDev ? ["'unsafe-eval'"] : []),
    ],
    "style-src": ["'self'", isDev ? "'unsafe-inline'" : `'nonce-${nonce}'`],
    // Inline style="" attributes (animation libraries, charts) cannot carry a nonce.
    "style-src-attr": ["'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", ...api],
    "font-src": ["'self'"],
    "connect-src": [
      "'self'",
      ...api,
      ...SENTRY,
      ...(isDev ? ["ws://localhost:*", "ws://*.localhost:*"] : []),
    ],
    // The policy viewer is an iframe of the API's own proxy; no other frame origin is allowed.
    "frame-src": [...STRIPE_FRAMES, ...TURNSTILE, ...api],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    "media-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  const parts = Object.entries(directives).map(([name, values]) => `${name} ${values.join(" ")}`);
  if (!isDev) parts.push("upgrade-insecure-requests");
  return parts.join("; ");
}

/** Paths where the browser may use geolocation (opt-in clock-in, plan.md 4.6 and T9.3). */
export const GEOLOCATION_PATH_PREFIXES = ["/clock"];

export function permissionsPolicy(pathname: string): string {
  const geolocation = GEOLOCATION_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
    ? "(self)"
    : "()";
  return `camera=(), microphone=(), geolocation=${geolocation}`;
}

/**
 * Files other sites may embed: the logo in our e-mails (opened in webmail on another site), link
 * previews and icons. Everything else is for this site and its subdomains only.
 */
export const EMBEDDABLE_PATH_PREFIXES = [
  "/brand/",
  "/opengraph-image",
  "/icon",
  "/apple-icon",
  "/favicon.ico",
];

/** Cross-Origin-Resource-Policy for a path (O6.1.7): who may load it as an image, script or frame. */
export function resourcePolicy(pathname: string): "same-site" | "cross-origin" {
  return EMBEDDABLE_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix))
    ? "cross-origin"
    : "same-site";
}

/** Headers every response gets, whatever the route. Also applied to static assets by next.config. */
export function baseSecurityHeaders(isProduction: boolean): Record<string, string> {
  return {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    // A page we open in a new tab, or that opens us, gets no handle on the other window (O6.1.7).
    "Cross-Origin-Opener-Policy": "same-origin",
    // The path-dependent value (resourcePolicy) replaces this where other sites may embed a file.
    "Cross-Origin-Resource-Policy": "same-site",
    // Browsers only honour HSTS over HTTPS; sending it from `next dev` would only confuse.
    ...(isProduction
      ? { "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload" }
      : {}),
  };
}

export function generateNonce(): string {
  return Buffer.from(crypto.randomUUID()).toString("base64");
}
