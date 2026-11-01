/** Status chips (plan 5.7): every status has a tone AND a text label, so colour is never the only signal. */

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export const STATUSES = {
  verified: { tone: "success", label: "Verified" },
  approved: { tone: "success", label: "Approved" },
  active: { tone: "success", label: "Active" },
  expiring: { tone: "warning", label: "Expiring" },
  expired: { tone: "danger", label: "Expired" },
  rejected: { tone: "danger", label: "Rejected" },
  pending: { tone: "info", label: "Pending" },
  open: { tone: "info", label: "Open" },
  "not-recorded": { tone: "neutral", label: "Not recorded" },
  draft: { tone: "neutral", label: "Draft" },
  closed: { tone: "neutral", label: "Closed" },
  archived: { tone: "neutral", label: "Archived" },
} as const satisfies Record<string, { tone: Tone; label: string }>;

export type StatusKey = keyof typeof STATUSES;

/** The tone for a status, or neutral for one this build has never heard of. */
export function statusTone(key: string): Tone {
  return key in STATUSES ? STATUSES[key as StatusKey].tone : "neutral";
}
