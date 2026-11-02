import type { components } from "@/lib/api/client";

import { shortDate } from "./holidays";

type Status = components["schemas"]["DocumentSlot"]["status"];

export const STATUS_TONE: Record<Status, "neutral" | "success" | "warning" | "danger"> = {
  missing: "neutral",
  current: "success",
  expiring: "warning",
  expired: "danger",
};

/** "Current", "Expires 3 Dec 2026", "Expired 3 Nov 2026": what a document's state means in words. */
export function expiryText(status: Status, expiresOn: string | null): string {
  if (status === "missing") return "Missing";
  if (!expiresOn) return "Current, no expiry";
  const when = shortDate(expiresOn);
  if (status === "expired") return `Expired ${when}`;
  return status === "expiring" ? `Expires ${when}` : `Current until ${when}`;
}
