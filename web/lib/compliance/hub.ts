import type { components } from "@/lib/api/client";

export type Overview = components["schemas"]["ComplianceOverview"];
export type Dossier = components["schemas"]["DossierOut"];
export type DossierLink = components["schemas"]["DossierLinkOut"];
export type ActivityCategory = (typeof ACTIVITY_CATEGORIES)[number][0];

export const ACTIVITY_CATEGORIES = [
  ["all", "All"],
  ["rtw", "Right to Work"],
  ["employees", "Employees"],
  ["attendance", "Attendance"],
  ["documents", "Documents"],
  ["changes", "Changes"],
] as const;

export const DOSSIER_SECTIONS = [
  ["licence", "Holding a licence"],
  ["rtw", "Right to Work"],
  ["sms", "SMS manuals"],
] as const;

export const EXPIRY_BUCKETS = [
  ["overdue", "Overdue"],
  ["next_30", "Next 30 days"],
  ["31_60", "31–60 days"],
  ["61_90", "61–90 days"],
] as const;
