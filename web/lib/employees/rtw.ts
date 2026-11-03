import type { components } from "@/lib/api/schema";
export type RTWStatus = components["schemas"]["RTWTab"]["status"];
export const RTW_LABEL: Record<RTWStatus, string> = {
  verified: "Verified",
  expiring: "Expiring",
  expired: "Expired",
  failed: "Failed",
  pending: "Pending",
  evidence_missing: "Evidence missing",
  not_recorded: "Not recorded",
};
export const RTW_TONE = {
  verified: "success",
  expiring: "warning",
  expired: "danger",
  failed: "danger",
  pending: "info",
  evidence_missing: "warning",
  not_recorded: "neutral",
} as const;
export const CHECK_TYPES = [
  { value: "online_share_code", label: "Home Office online check" },
  { value: "idsp_digital", label: "Digital identity check (IDSP)" },
  { value: "manual_list_a", label: "Manual check — List A" },
  { value: "manual_list_b", label: "Manual check — List B" },
] as const;
export const RTW_FILTERS = [
  { value: "all", label: "All statuses" },
  { value: "NeedsAttention", label: "Needs attention" },
  { value: "Verified", label: "Verified" },
  { value: "Expiring", label: "Expiring" },
  { value: "EvidenceMissing", label: "Evidence missing" },
  { value: "Expired", label: "Expired or failed" },
  { value: "Pending", label: "Pending" },
  { value: "NotRecorded", label: "Not recorded" },
] as const;
export type RTWFilter = (typeof RTW_FILTERS)[number]["value"];
export function rtwFilterFromParam(value: string | string[] | undefined): RTWFilter {
  const single = Array.isArray(value) ? value[0] : value;
  return RTW_FILTERS.find((f) => f.value === single)?.value ?? "all";
}
export function rtwMatches(status: RTWStatus, filter: RTWFilter): boolean {
  if (filter === "all") return true;
  if (filter === "NeedsAttention") return status !== "verified";
  if (filter === "Expired") return status === "expired" || status === "failed";
  return RTW_LABEL[status].replaceAll(" ", "").toLowerCase() === filter.toLowerCase();
}
