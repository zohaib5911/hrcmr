"use client";

import { Link2Off, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import {
  ALL,
  filterUsers,
  fullName,
  NO_FILTERS,
  unlinkedBanner,
  type AccessUser,
  type Filters,
} from "@/lib/company/access";
import { ROLE_LABELS, type Role } from "@/lib/auth/roles";

type AccessList = components["schemas"]["AccessList"];

const ROLES = Object.keys(ROLE_LABELS) as Role[];

const COLUMNS: Column<AccessUser>[] = [
  {
    id: "user",
    header: "User",
    primary: true,
    sortValue: (u) => fullName(u).toLowerCase(),
    exportValue: (u) => `${fullName(u)} <${u.email}>`,
    cell: (u) => (
      <div className="flex items-center gap-3">
        <Avatar name={fullName(u)} size="sm" decorative />
        <div className="min-w-0">
          <p className="text-body text-label truncate">
            {fullName(u)}
            {u.is_you ? <span className="text-secondary-label"> (you)</span> : null}
          </p>
          <p className="text-footnote text-secondary-label truncate">{u.email}</p>
        </div>
      </div>
    ),
  },
  {
    id: "role",
    header: "Role",
    sortValue: (u) => ROLE_LABELS[u.role],
    cell: (u) => ROLE_LABELS[u.role],
  },
  {
    id: "status",
    header: "Status",
    sortValue: (u) => u.status,
    cell: (u) => (
      <StatusChip tone={u.status === "active" ? "success" : "warning"}>
        {u.status === "active" ? "Active" : "Suspended"}
      </StatusChip>
    ),
  },
  {
    id: "two_step",
    header: "Two-step",
    sortValue: (u) => (u.two_step ? 1 : 0),
    exportValue: (u) => (u.two_step ? "On" : "Off"),
    cell: (u) => (
      <StatusChip tone={u.two_step ? "success" : "neutral"}>{u.two_step ? "On" : "Off"}</StatusChip>
    ),
  },
  {
    id: "employee",
    header: "Linked employee",
    sortValue: (u) => (u.employee_id ? 1 : 0),
    exportValue: (u) => (u.employee_id ? "Linked" : "Not linked"),
    cell: (u) =>
      u.employee_id ? "Linked" : <span className="text-secondary-label">Not linked</span>,
  },
];

/** `/company/users` (plan 8.15): everyone who can sign in, with filters and the unlinked banner. */
export function UserAccessPage({ list }: { list: AccessList }) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const shown = useMemo(() => filterUsers(list.users, filters), [list.users, filters]);
  const banner = unlinkedBanner(list.unlinked);
  const filtering =
    filters.role !== ALL || filters.status !== ALL || filters.search.trim().length > 0;

  return (
    <>
      <PageHeader
        title="User access"
        description="Everyone who can sign in to your company, and what they can do."
      />
      <div className="flex flex-col gap-4">
        {banner ? (
          <Alert tone="warning" title={banner}>
            These people can sign in but are not yet linked to an employee record. You can link them
            once employees are added.
          </Alert>
        ) : null}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <SearchField
            label="Search people"
            listSearch
            containerClassName="sm:w-72"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          />
          <Select
            label="Role"
            value={filters.role}
            onChange={(e) => setFilters({ ...filters, role: e.target.value })}
          >
            <option value={ALL}>All roles</option>
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </Select>
          <Select
            label="Status"
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <option value={ALL}>All statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </Select>
        </div>
        <DataTable
          caption="People with access"
          columns={COLUMNS}
          rows={shown}
          getRowId={(u) => u.id}
          defaultSort={{ column: "user", direction: "asc" }}
          empty={
            <EmptyState
              icon={filtering ? Link2Off : Users}
              title={filtering ? "Nobody matches" : "No one here yet"}
              description={
                filtering
                  ? "Try a different search or clear the filters."
                  : "People you invite will appear here."
              }
            />
          }
        />
      </div>
    </>
  );
}
