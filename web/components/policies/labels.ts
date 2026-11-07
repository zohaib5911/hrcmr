import type { components } from "@/lib/api/client";

export type PolicyOut = components["schemas"]["PolicyOut"];
export type PolicyRecipient = components["schemas"]["PolicyRecipient"];
export type OwnPolicy = components["schemas"]["OwnPolicy"];
export type PolicyReceipt = components["schemas"]["PolicyReceipt"];
export type PolicyCategory = PolicyOut["category"];
export type AudienceType = PolicyOut["audience_type"];
export type ConfirmationMode = PolicyOut["confirmation_mode"];

/** Exhaustive: TypeScript fails here if the API adds a category this screen does not name. */
export const CATEGORY_LABELS: Record<PolicyCategory, string> = {
  employment_contract: "Employment contract",
  job_description: "Job description",
  offer_letter: "Offer letter",
  contract_change: "Contract change letter",
  company_policy: "Company policy (general)",
  employee_handbook: "Employee handbook",
  code_of_conduct: "Code of conduct",
  it_email_social_media: "IT, email and social media",
  drugs_alcohol: "Drugs and alcohol",
  sickness_sick_pay: "Sickness and sick pay",
  attendance_punctuality: "Attendance and punctuality",
  holiday_annual_leave: "Holiday and annual leave",
  flexible_hybrid_working: "Flexible and hybrid working",
  family_leave: "Family leave",
  equality_diversity: "Equality and diversity",
  anti_harassment: "Anti-harassment and bullying",
  grievance: "Grievance",
  disciplinary: "Disciplinary",
  whistleblowing: "Whistleblowing",
  health_safety: "Health and safety",
  privacy_notice: "Employee privacy notice",
  sponsor_duties: "Sponsor duties notice (visa and sponsorship)",
  other: "Other",
};

export const AUDIENCE_LABELS: Record<AudienceType, string> = {
  everyone: "Everyone",
  departments: "Departments",
  locations: "Locations",
  named: "Named people",
  visa_holders: "Employees with a visa on file",
};

export const MODE_LABELS: Record<ConfirmationMode, string> = {
  accept: "Read and accept",
  sign: "Read and sign",
};

export const POLICY_STATUS = {
  draft: { label: "Draft", tone: "neutral" },
  sent: { label: "Sent", tone: "info" },
  archived: { label: "Archived", tone: "neutral" },
} as const;

export const ACCEPTANCE_STATUS = {
  pending: { label: "Pending", tone: "info" },
  accepted: { label: "Accepted", tone: "success" },
  signed: { label: "Signed", tone: "success" },
  overdue: { label: "Overdue", tone: "danger" },
} as const;

/** Files the viewer can show inline; anything else is downloaded. */
export const VIEWABLE_MIME = ["application/pdf", "image/jpeg", "image/png"] as const;

export function percent(done: number, total: number): number {
  return total === 0 ? 0 : Math.round((done / total) * 100);
}
