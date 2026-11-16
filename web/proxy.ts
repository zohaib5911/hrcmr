/**
 * The request proxy (called `middleware` before Next.js 16): host routing, a per-request CSP
 * nonce, and the security headers. It holds no secrets and calls no third-party service.
 */

import { NextResponse, type NextRequest } from "next/server";

import {
  baseSecurityHeaders,
  buildCsp,
  generateNonce,
  originOf,
  permissionsPolicy,
  resourcePolicy,
} from "@/lib/security/csp";
import { classifyHost, decideRoute, hostnameOf } from "@/lib/security/hosts";

const NOT_FOUND_PATH = "/__not_found__";

/**
 * A rewrite destination on the origin Next.js itself uses for this request.
 *
 * It must come from `request.url`, not from the Host header and not from `request.nextUrl`:
 * Next.js treats a rewrite to any other origin as an EXTERNAL proxy, issuing a brand new HTTP
 * request that re-runs this proxy with a different Host. (`nextUrl` rewrites 127.x.x.x to
 * `localhost`, so cloning it breaks whenever the server is bound to a loopback address.) The Host
 * header is used only to decide which kind of host this is.
 *
 * Even so, Next.js compares origins using the address the server is bound to, so the server must
 * listen on 0.0.0.0 (as the Docker image does) or `next dev`'s default. Bound to a loopback address
 * such as 127.0.0.1 the admin rewrite is treated as external and fails with a 500: closed, never
 * exposing admin pages. tests/e2e covers the working configuration.
 */
function sameOrigin(request: NextRequest, pathname: string): URL {
  return new URL(`${pathname}${request.nextUrl.search}`, request.url);
}

export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const kind = classifyHost(
    hostnameOf(request.headers.get("host")),
    process.env.NEXT_PUBLIC_ADMIN_URL,
  );
  const decision = decideRoute(kind, pathname);

  const isProduction = process.env.NODE_ENV === "production";
  const nonce = generateNonce();
  const csp = buildCsp({
    nonce,
    isDev: !isProduction,
    apiOrigin: originOf(process.env.NEXT_PUBLIC_API_URL),
  });

  // Next.js reads the nonce from the request's CSP header while it renders the page.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  // The public path, for the admin frame: it sends a person with no platform session to start one.
  requestHeaders.set("x-pathname", pathname);
  requestHeaders.set("Content-Security-Policy", csp);

  let response: NextResponse;
  if (decision.action === "not-found") {
    response = NextResponse.rewrite(sameOrigin(request, NOT_FOUND_PATH), {
      request: { headers: requestHeaders },
      status: 404,
    });
  } else if (decision.action === "rewrite") {
    response = NextResponse.rewrite(sameOrigin(request, decision.pathname), {
      request: { headers: requestHeaders },
    });
  } else {
    response = NextResponse.next({ request: { headers: requestHeaders } });
  }

  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Permissions-Policy", permissionsPolicy(pathname));
  for (const [name, value] of Object.entries(baseSecurityHeaders(isProduction))) {
    response.headers.set(name, value);
  }
  response.headers.set("Cross-Origin-Resource-Policy", resourcePolicy(pathname));
  if (kind === "admin") response.headers.set("X-Robots-Tag", "noindex, nofollow");
  return response;
}

export const config = {
  // Static assets and the health check skip the proxy; next.config.ts gives assets their headers.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|healthz).*)"],
};
