/**
 * Host-based routing (plan.md section 3 and T0.6).
 *
 * One Next.js service answers for two kinds of host:
 *   - the main host (DOMAIN, staging.DOMAIN):        marketing site and the company app;
 *   - the admin host (admin.DOMAIN, admin.staging…): the super-admin back office.
 *
 * Route groups such as `(admin)` do not appear in URLs, so the super-admin pages live under a real
 * internal segment, `/platform`. The proxy rewrites `admin.DOMAIN/companies` to
 * `/platform/companies`, and the internal segment is unreachable from the outside: asking for
 * `/platform/...` directly, on any host, is a 404. The admin pages therefore exist ONLY on the
 * admin host, alongside the shared public brand images.
 */

export type HostKind = "admin" | "main";

export const ADMIN_SEGMENT = "/platform";

export type RouteDecision =
  { action: "next" } | { action: "rewrite"; pathname: string } | { action: "not-found" };

/** `Admin.Example.com:3000` -> `admin.example.com`. IPv6 literals keep their brackets. */
export function hostnameOf(hostHeader: string | null | undefined): string {
  const host = (hostHeader ?? "").trim().toLowerCase();
  if (host.startsWith("[")) {
    const end = host.indexOf("]");
    return end === -1 ? host : host.slice(0, end + 1);
  }
  return host.split(":")[0] ?? "";
}

/**
 * The admin host is the configured one (NEXT_PUBLIC_ADMIN_URL) or any host that starts with
 * `admin.` (admin.localhost in development, admin.staging.DOMAIN on staging).
 */
export function classifyHost(hostname: string, adminUrl?: string): HostKind {
  if (adminUrl) {
    try {
      if (new URL(adminUrl).hostname.toLowerCase() === hostname) return "admin";
    } catch {
      // A malformed setting must not take the site down; the prefix rule below still applies.
    }
  }
  return hostname.startsWith("admin.") ? "admin" : "main";
}

/**
 * The path as the router will see it: percent-decoded once, `.` and `..` resolved, repeated slashes
 * collapsed, and lower-cased. Used ONLY to compare against the internal segment, so that
 * `/%70latform`, `/Platform` and `/x/../platform` are all recognised as `/platform`.
 */
export function normalizeForComparison(pathname: string): string {
  let decoded = pathname;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    // Malformed escapes stay as they are; the router will reject them.
  }
  const stack: string[] = [];
  for (const part of decoded.split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") stack.pop();
    else stack.push(part);
  }
  return `/${stack.join("/")}`.toLowerCase();
}

export function isInternalAdminPath(pathname: string): boolean {
  const path = normalizeForComparison(pathname);
  return path === ADMIN_SEGMENT || path.startsWith(`${ADMIN_SEGMENT}/`);
}

/** Dot segments, encoded dots/slashes/backslashes and doubled slashes: never legitimate here. */
const AMBIGUOUS_PATH = /(^|\/)\.\.?(\/|$)|%2e|%2f|%5c|\\|\/\//i;

export function decideRoute(kind: HostKind, pathname: string): RouteDecision {
  if (isInternalAdminPath(pathname)) return { action: "not-found" };
  if (kind === "main") return { action: "next" };
  // Only plain paths are mapped onto the admin segment, so an encoded `..` cannot climb out of it.
  if (AMBIGUOUS_PATH.test(pathname)) return { action: "not-found" };
  // Shared, repository-owned artwork and metadata images also belong on the admin host.
  if (
    /^\/brand\/[a-z0-9-]+\.(svg|png)$/.test(pathname) ||
    /^\/(icon\d*|apple-icon)\.png$/.test(pathname) ||
    pathname === "/opengraph-image"
  )
    return { action: "next" };
  return {
    action: "rewrite",
    pathname: pathname === "/" ? ADMIN_SEGMENT : `${ADMIN_SEGMENT}${pathname}`,
  };
}
