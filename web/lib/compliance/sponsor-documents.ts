import type { components } from "@/lib/api/schema";

export type SponsorDocument = components["schemas"]["SponsorDocumentOut"];
export type DocumentType = SponsorDocument["doc_type"];
export const DOCUMENT_TYPES = [
  { value: "visa", label: "Visa" },
  { value: "passport", label: "Passport" },
  { value: "dbs", label: "DBS certificate" },
  { value: "euss", label: "EUSS status" },
  { value: "national_id", label: "National ID" },
  { value: "other", label: "Other" },
] as const;
export const VISA_ROUTES = [
  { value: "skilled_worker", label: "Skilled Worker" },
  { value: "health_care_worker", label: "Health and Care Worker" },
  { value: "global_business_mobility", label: "Global Business Mobility" },
  { value: "scale_up", label: "Scale-up" },
  { value: "temporary_worker", label: "Temporary Worker" },
  { value: "graduate", label: "Graduate" },
  { value: "student", label: "Student" },
  { value: "euss_settled", label: "EUSS settled" },
  { value: "euss_pre_settled", label: "EUSS pre-settled" },
  { value: "family", label: "Family" },
  { value: "other", label: "Other" },
] as const;
export const DOCUMENT_STATUS = {
  current: { label: "Current", tone: "success" },
  expiring: { label: "Expiring", tone: "warning" },
  expired: { label: "Expired", tone: "danger" },
  evidence_missing: { label: "Evidence missing", tone: "warning" },
  superseded: { label: "Superseded", tone: "neutral" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
} as const;
export const documentLabel = (type: DocumentType) =>
  DOCUMENT_TYPES.find((t) => t.value === type)!.label;
export const routeLabel = (route: string | null) =>
  VISA_ROUTES.find((r) => r.value === route)?.label ?? "Not set";
