import type { paths } from "@/lib/api/client";

export const PAGE_SIZE = 50;
export function pageOffset(value: string | undefined): number {
  const n = Number(value ?? 0);
  return Number.isSafeInteger(n) && n >= 0 && n <= 100_000 ? n : 0;
}
export type AuditFilters = NonNullable<paths["/platform/audit"]["get"]["parameters"]["query"]>;
export function auditFilters(params: Record<string, string | string[] | undefined>): AuditFilters {
  const query: AuditFilters = {};
  if (typeof params.action === "string" && params.action.trim())
    query.action = params.action.trim().slice(0, 100);
  if (params.actor_type === "system" || params.actor_type === "platform_admin")
    query.actor_type = params.actor_type;
  for (const key of ["since", "until"] as const) {
    const value = params[key];
    if (
      typeof value === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(value) &&
      Number.isFinite(Date.parse(value))
    ) {
      query[key] = `${value}T${key === "since" ? "00:00:00" : "23:59:59.999999"}Z`;
    }
  }
  return query;
}
export function queryString(query: Record<string, string | number | null | undefined>): string {
  return new URLSearchParams(
    Object.entries(query).flatMap(([k, v]) => (v == null ? [] : [[k, String(v)]])),
  ).toString();
}
