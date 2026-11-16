import path from "node:path";

import createMDX from "@next/mdx";

import type { NextConfig } from "next";

import {
  EMBEDDABLE_PATH_PREFIXES,
  baseSecurityHeaders,
  permissionsPolicy,
} from "./lib/security/csp";

// The repository root: brand.config.ts lives there, outside this folder.
const repoRoot = path.resolve(process.cwd(), "..");

const isProduction = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  // Files named `page.dev.tsx` (the /design page) are routes only in development. In a production
  // build they are not pages at all: not compiled, not served, not in the bundle.
  pageExtensions: isProduction ? ["tsx", "ts", "jsx", "js"] : ["tsx", "ts", "jsx", "js", "dev.tsx"],
  // A self-contained server for the Docker image.
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  // Downloads read reviewed documents from disk in the standalone server.
  outputFileTracingIncludes: {
    "/opengraph-image": ["./public/brand/logo.svg"],
    "/clock/icon": ["./public/brand/clock-*.png"],
    "/resources/templates/download/*": ["./content/templates/*"],
  },
  turbopack: { root: repoRoot },
  poweredByHeader: false,
  reactStrictMode: true,
  typedRoutes: true,
  // Static assets bypass the proxy, so they get the base security headers here. The proxy sets
  // the per-request Content-Security-Policy and the same base headers on every page.
  async headers() {
    const headers = Object.entries(baseSecurityHeaders(isProduction)).map(([key, value]) => ({
      key,
      value,
    }));
    // The Permissions-Policy of a PAGE depends on its path, so the proxy sets it. The routes the
    // proxy skips (the `matcher` exclusions in proxy.ts) never need a browser feature, so they get
    // the strictest value here. Pages are not listed, or this would overwrite the proxy's value.
    const unproxied = ["/_next/static/:path*", "/_next/image", "/favicon.ico", "/healthz"];
    // Files other sites may embed (the e-mail logo, link previews, icons). Listed after the
    // catch-all, so this Cross-Origin-Resource-Policy wins; proxy.ts sets the same per path.
    const embeddable = EMBEDDABLE_PATH_PREFIXES.map((prefix) =>
      prefix.endsWith("/") ? `${prefix}:path*` : `${prefix}(.*)`,
    );
    return [
      { source: "/:path*", headers },
      ...unproxied.map((source) => ({
        source,
        headers: [{ key: "Permissions-Policy", value: permissionsPolicy("/") }],
      })),
      ...embeddable.map((source) => ({
        source,
        headers: [{ key: "Cross-Origin-Resource-Policy", value: "cross-origin" }],
      })),
    ];
  },
};

const withMDX = createMDX({
  options: {
    // String path keeps the build-time guard compatible with Turbopack.
    remarkPlugins: [path.resolve(process.cwd(), "scripts/remark-safe-guides.mjs")],
  },
});

export default withMDX(nextConfig);
