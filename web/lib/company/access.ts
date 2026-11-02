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
