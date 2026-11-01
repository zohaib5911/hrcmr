import path from "node:path";

import type { NextConfig } from "next";

import { baseSecurityHeaders, permissionsPolicy } from "./lib/security/csp";

// The repository root: brand.config.ts lives there, outside this folder.
const repoRoot = path.resolve(process.cwd(), "..");

const nextConfig: NextConfig = {
  // A self-contained server for the Docker image.
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  poweredByHeader: false,
  reactStrictMode: true,
  typedRoutes: true,
  // Static assets bypass the proxy, so they get the base security headers here. The proxy sets
  // the per-request Content-Security-Policy and the same base headers on every page.
  async headers() {
    const headers = Object.entries(baseSecurityHeaders(process.env.NODE_ENV === "production")).map(
      ([key, value]) => ({ key, value }),
    );
    // The Permissions-Policy of a PAGE depends on its path, so the proxy sets it. The routes the
    // proxy skips (the `matcher` exclusions in proxy.ts) never need a browser feature, so they get
    // the strictest value here. Pages are not listed, or this would overwrite the proxy's value.
    const unproxied = ["/_next/static/:path*", "/_next/image", "/favicon.ico", "/healthz"];
    return [
      { source: "/:path*", headers },
      ...unproxied.map((source) => ({
        source,
        headers: [{ key: "Permissions-Policy", value: permissionsPolicy("/") }],
      })),
    ];
  },
};

export default nextConfig;
