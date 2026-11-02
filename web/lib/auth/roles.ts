import type { components } from "@/lib/api/client";

export type Role = components["schemas"]["InvitationDetails"]["role"];

/** How a role is named to people (plan 7). */
export const ROLE_LABELS: Record<Role, string> = {
  company_admin: "Company Admin",
  hr_admin: "HR Admin",
  people_manager: "People Manager",
  recruiter: "Recruiter",
  employee: "Employee",
  read_only_auditor: "Read-only Auditor",
};
