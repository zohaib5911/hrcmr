import type { components } from "@/lib/api/client";

export type RtwStatus = components["schemas"]["CheckOut"]["status"];
export type RtwCheckType = components["schemas"]["CheckIn"]["check_type"];
export type RtwOutcome = components["schemas"]["CheckIn"]["outcome"];

export const RTW_STATUS: Record<
  RtwStatus,
  { label: string; tone: "neutral" | "success" | "warning" | "info" | "danger" }
> = {
  verified: { label: "Verified", tone: "success" },
  expiring: { label: "Expiring", tone: "warning" },
  expired: { label: "Expired", tone: "danger" },
  failed: { label: "Failed", tone: "danger" },
  pending: { label: "Pending", tone: "info" },
  evidence_missing: { label: "Evidence missing", tone: "warning" },
  not_recorded: { label: "Not recorded", tone: "neutral" },
};

export const CHECK_TYPE: Record<RtwCheckType, string> = {
  online_share_code: "Online share code",
  idsp_digital: "Digital identity (IDSP)",
  manual_list_a: "Manual check: List A document",
  manual_list_b: "Manual check: List B document",
};

export const OUTCOME: Record<RtwOutcome, string> = {
  pending: "Pending",
  verified: "Verified",
  failed: "Failed",
};
