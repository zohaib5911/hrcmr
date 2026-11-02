import type { components } from "@/lib/api/client";

export type EmployeeProfile = components["schemas"]["EmployeeProfile"];
export type EmployeeStatus = EmployeeProfile["status"];

const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2 Nov 2026". Written out here so it reads the same in every browser. */
export function shortDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTH[(month ?? 1) - 1]} ${year}`;
}

/** "today", "3 days ago", "5 weeks ago", "4 months ago", "2 years ago", or "in 12 days" for a date ahead. */
export function relative(iso: string, today: string): string {
  const days = Math.round((Date.parse(today) - Date.parse(iso)) / 86_400_000);
  if (days === 0) return "today";
  const ahead = days < 0;
  const n = Math.abs(days);
  const plural = (count: number, unit: string) => `${count} ${unit}${count === 1 ? "" : "s"}`;
  let span: string;
  if (n < 14) span = plural(n, "day");
  else if (n < 60) span = plural(Math.floor(n / 7), "week");
  else if (n < 730) span = plural(Math.floor(n / 30.4), "month");
  else span = plural(Math.floor(n / 365.25), "year");
  return ahead ? `in ${span}` : `${span} ago`;
}

/** "Joined 2 Nov 2026 · 3 days ago". */
export function joinedLine(hireDate: string, today: string): string {
  const verb = Date.parse(hireDate) > Date.parse(today) ? "Joins" : "Joined";
  return `${verb} ${shortDate(hireDate)} · ${relative(hireDate, today)}`;
}

/** The buttons in "Access & status": the states a record can be moved to from where it is. */
export const MOVES: Record<
  EmployeeStatus,
  readonly { to: EmployeeStatus; label: string; prompt: string }[]
> = {
  active: [
    { to: "on_leave", label: "Set to on leave", prompt: "Set to on leave?" },
    { to: "leaver", label: "Set to leaver", prompt: "Mark as a leaver?" },
    { to: "archived", label: "Archive", prompt: "Archive this record?" },
  ],
  on_leave: [
    { to: "active", label: "Back to active", prompt: "Mark as back at work?" },
    { to: "leaver", label: "Set to leaver", prompt: "Mark as a leaver?" },
    { to: "archived", label: "Archive", prompt: "Archive this record?" },
  ],
  leaver: [
    { to: "active", label: "Re-activate", prompt: "Re-activate this person?" },
    { to: "archived", label: "Archive", prompt: "Archive this record?" },
  ],
  archived: [{ to: "active", label: "Restore", prompt: "Restore this record?" }],
};
