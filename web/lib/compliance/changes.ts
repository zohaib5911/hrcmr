import type { components } from "@/lib/api/schema";

export type Change = components["schemas"]["ChangeOut"];
export type OrgChange = components["schemas"]["OrgChangeOut"];
export type Reporting = Change | OrgChange;
export const CHANGE_TYPES = [
  { value: "did_not_start", label: "Didn't start work" },
  { value: "unauthorised_absence", label: "Unauthorised absence of more than 10 working days" },
  { value: "sponsorship_stopped", label: "Left, or sponsorship stopped" },
  { value: "salary_reduced", label: "Salary reduced" },
  { value: "job_or_soc_changed", label: "Change of job or SOC code" },
  { value: "work_location_changed", label: "Change of main work location" },
  { value: "working_hours_changed", label: "Change in working hours" },
  {
    value: "unpaid_reduced_absence",
    label: "Unpaid or reduced-pay absence over 4 weeks in a year",
  },
  { value: "other", label: "Other reportable change" },
] as const;
export const ORG_CHANGE_TYPES = [
  { value: "address", label: "Address changed" },
  { value: "ownership", label: "Ownership changed" },
  { value: "name", label: "Organisation name changed" },
  { value: "key_personnel", label: "Other key personnel changed" },
  { value: "ao_or_key_contact", label: "Authorising Officer or Key Contact replacement" },
  { value: "other", label: "Other organisation change" },
] as const;
export const CHANGE_FILTERS = [
  { value: "all", label: "All" },
  { value: "unreported", label: "Still to report" },
  { value: "overdue", label: "Past the deadline" },
] as const;
export type ChangeFilter = (typeof CHANGE_FILTERS)[number]["value"];
export const changeLabel = (record: Reporting) =>
  ("employee_id" in record ? CHANGE_TYPES : ORG_CHANGE_TYPES).find(
    (t) => t.value === record.change_type,
  )?.label ?? record.change_type;
export const STATUS = {
  reported: { label: "Reported", tone: "success" },
  unreported: { label: "Still to report", tone: "info" },
  overdue: { label: "Past deadline", tone: "danger" },
  prompt: { label: "Report promptly", tone: "warning" },
} as const;
export const SPONSOR_GUIDANCE =
  "https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance-accessible";
export const SPONSOR_GLOSSARY =
  "https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-glossary/workers-and-temporary-workers-guidance-for-sponsors-glossary-accessible#working-days";
export const CHECKED_ON = "3 Nov 2026";
