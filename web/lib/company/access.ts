import type { components } from "@/lib/api/client";

export type AccessUser = components["schemas"]["AccessUser"];

export const ALL = "all";

export interface Filters {
  role: string;
  status: string;
  search: string;
}

export const NO_FILTERS: Filters = { role: ALL, status: ALL, search: "" };

/** The people the filters leave: a role, a status, and words found in the name or e-mail. */
export function filterUsers(users: readonly AccessUser[], filters: Filters): AccessUser[] {
  const words = filters.search.toLowerCase().split(/\s+/).filter(Boolean);
  return users.filter((user) => {
    if (filters.role !== ALL && user.role !== filters.role) return false;
    if (filters.status !== ALL && user.status !== filters.status) return false;
    const haystack = `${user.first_name} ${user.last_name} ${user.email}`.toLowerCase();
    return words.every((word) => haystack.includes(word));
  });
}

/** "1 unlinked user" / "3 unlinked users", or null when everyone is linked. */
export function unlinkedBanner(count: number): string | null {
  if (count <= 0) return null;
  return `${count} unlinked ${count === 1 ? "user" : "users"}`;
}

export function fullName(user: Pick<AccessUser, "first_name" | "last_name">): string {
  return `${user.first_name} ${user.last_name}`.trim();
}

export const ROLE_DESCRIPTIONS: Record<AccessUser["role"], string> = {
  company_admin: "Full control, including roles, billing and company settings.",
  hr_admin: "Runs HR day to day: employees, leave, documents and compliance.",
  people_manager: "Sees and approves requests for their own team.",
  recruiter: "Manages job postings, candidates and offers.",
  employee: "Sees their own record, leave and documents.",
  read_only_auditor: "Reads everything for an audit and changes nothing.",
};

export type RowAction = "role" | "suspend" | "reactivate" | "reset" | "resend" | "cancel";

export interface Viewer {
  role: string;
  canInvite: boolean;
  canAssign: boolean;
}

/**
 * The actions to offer for one row. The API decides what is allowed; this only hides what would be
 * refused: a pending invitation can be resent or cancelled, a member's role changed, suspended or
 * reactivated, and two-step reset when they have it. Nobody acts on themselves, and only a Company
 * Admin acts on a Company Admin.
 */
export function rowActions(user: AccessUser, viewer: Viewer): RowAction[] {
  if (user.status === "invited") {
    const mayInvite =
      viewer.canInvite && (user.role !== "company_admin" || viewer.role === "company_admin");
    return mayInvite ? ["resend", "cancel"] : [];
  }
  if (!viewer.canAssign || user.is_you) return [];
  if (user.role === "company_admin" && viewer.role !== "company_admin") return [];
  const actions: RowAction[] = ["role", user.status === "active" ? "suspend" : "reactivate"];
  if (user.two_step) actions.push("reset");
  return actions;
}
