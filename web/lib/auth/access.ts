/**
 * What the signed-in person's role lets them see in the navigation (plan 5.6 and 7). The API checks
 * every request whatever this says; hiding what someone cannot use only keeps the menu tidy.
 */
import { NAV_GROUPS, type NavGroup } from "@/lib/navigation";

/**
 * To see a page you need at least one of these permissions. A page that is not listed is for
 * everyone who is signed in.
 */
export const NAV_PERMISSIONS: Readonly<Record<string, readonly string[]>> = {
  employees: ["employee.profile.read", "employee.profile.read_reports"],
  recruitment: [
    "recruitment.posting.read",
    "recruitment.candidate.read",
    "recruitment.requisition.read",
  ],
  organogram: ["organogram.level.read"],
  learning: [
    "learning.assignment.read",
    "learning.assignment.read_reports",
    "learning.assignment.read_own",
  ],
  compliance: ["compliance.overview.read"],
  "migrant-employees": ["employee.rtw.read"],
  reminders: ["compliance.reminder.send", "compliance.overview.read"],
  checker: ["soc.check.read", "soc.check.run"],
  documents: ["document.file.read"],
  policies: ["policy.document.read", "policy.acceptance.read_own"],
  reports: ["document.report.generate"],
  leave: [
    "leave.request.read",
    "leave.request.read_own",
    "leave.balance.read_own",
    "leave.request.create_own",
  ],
  attendance: ["attendance.record.read", "attendance.record.read_own"],
  rota: ["rota.shift.read", "rota.scheduled_shift.read_own", "rota.duty_roster.read"],
  "work-log": ["work_log.entry.read", "work_log.entry.read_own"],
  "my-documents": ["document.file.read_own"],
  company: ["company.overview.read", "company.profile.read"],
  users: ["rbac.user.read"],
  billing: ["billing.manage"],
};

export function can(permissions: readonly string[], ...wanted: string[]): boolean {
  return wanted.some((permission) => permissions.includes(permission));
}

/**
 * The navigation for someone with these permissions. `null` (not known yet) shows everything, so a
 * slow session never makes the menu jump from short to long.
 */
export function visibleGroups(
  permissions: readonly string[] | null,
  groups: readonly NavGroup[] = NAV_GROUPS,
): readonly NavGroup[] {
  if (permissions === null) return groups;
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        const needs = NAV_PERMISSIONS[item.id];
        return !needs || can(permissions, ...needs);
      }),
    }))
    .filter((group) => group.items.length > 0);
}
