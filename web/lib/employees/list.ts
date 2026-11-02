import type { components } from "@/lib/api/client";

export type EmployeeRow = components["schemas"]["EmployeeRow"];
export type EmployeeSummary = components["schemas"]["EmployeeSummary"];

export const PILLS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "on_leave", label: "On leave" },
  { id: "leaver", label: "Leavers" },
] as const;

export type PillId = (typeof PILLS)[number]["id"];

export const STATUS_LABEL: Record<EmployeeRow["status"], string> = {
  active: "Active",
  on_leave: "On leave",
  leaver: "Leaver",
  archived: "Archived",
};

/** A quick pill from a deep link such as `/employees?status=active`; anything else is "All". */
export function pillFromParam(value: string | string[] | undefined): PillId {
  const single = Array.isArray(value) ? value[0] : value;
  return PILLS.find((pill) => pill.id === single)?.id ?? "all";
}

export interface Filters {
  pill: PillId;
  department: string;
  search: string;
}

export const ALL_DEPARTMENTS = "all";

/** The employees the pill, department and search leave (name or number, ignoring case and spaces). */
export function filterEmployees(rows: readonly EmployeeRow[], filters: Filters): EmployeeRow[] {
  const words = filters.search.toLowerCase().split(/\s+/).filter(Boolean);
  return rows.filter((row) => {
    if (filters.pill !== "all" && row.status !== filters.pill) return false;
    if (filters.department !== ALL_DEPARTMENTS && row.department !== filters.department) {
      return false;
    }
    const name = `${row.first_name} ${row.last_name}`.toLowerCase();
    const number = row.employee_number.toLowerCase().replace(/\s+/g, "");
    return words.every((word) => name.includes(word) || number.includes(word));
  });
}

/** "12 employees · 10 active · 1 on leave · 1 leaver". Zero counts are left out. */
export function summaryLine(summary: EmployeeSummary): string {
  const parts = [`${summary.total} ${summary.total === 1 ? "employee" : "employees"}`];
  if (summary.active > 0) parts.push(`${summary.active} active`);
  if (summary.on_leave > 0) parts.push(`${summary.on_leave} on leave`);
  if (summary.leavers > 0)
    parts.push(`${summary.leavers} ${summary.leavers === 1 ? "leaver" : "leavers"}`);
  return parts.join(" · ");
}

/** The departments that appear in the list, for the department filter. */
export function departmentsIn(rows: readonly EmployeeRow[]): string[] {
  return [...new Set(rows.map((r) => r.department).filter((d): d is string => !!d))].sort((a, b) =>
    a.localeCompare(b),
  );
}
