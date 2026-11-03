"use client";

import { KeyRound, Link2Off, Pencil, Send, UserCheck, UserX, Users, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan, useMe } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { MenuItem, MenuSeparator } from "@/components/ui/menu";
import { SearchField } from "@/components/ui/search-field";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { attempt } from "@/lib/auth/request";
import type { components } from "@/lib/api/client";
import {
  ALL,
  filterUsers,
  fullName,
  NO_FILTERS,
  rowActions,
  unlinkedBanner,
  type RowAction,
  type AccessUser,
  type Filters,
} from "@/lib/company/access";
import { ROLE_LABELS, type Role } from "@/lib/auth/roles";

import { EmployeeLinkSheet } from "./employee-link-sheet";
import { RolesViewer } from "./roles-viewer";
import { TwoStepPolicyCard } from "./two-step-policy";
import { ConfirmSheet, InviteSheet, RoleSheet } from "./user-access-sheets";

type AccessList = components["schemas"]["AccessList"];
type TwoStepPolicy = components["schemas"]["TwoStepPolicy"];
type RoleMatrix = components["schemas"]["RoleMatrix"];

const ROLES = Object.keys(ROLE_LABELS) as Role[];

const STATUS_LABEL = { active: "Active", suspended: "Suspended", invited: "Invited" } as const;
const STATUS_TONE = { active: "success", suspended: "warning", invited: "info" } as const;

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
    cell: (u) => <StatusChip tone={STATUS_TONE[u.status]}>{STATUS_LABEL[u.status]}</StatusChip>,
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

const ACTION_ITEMS: Record<
  RowAction,
  { label: string; icon: typeof Pencil; destructive?: boolean }
> = {
  role: { label: "Change role", icon: Pencil },
  suspend: { label: "Suspend", icon: UserX, destructive: true },
  reactivate: { label: "Reactivate", icon: UserCheck },
  reset: { label: "Reset two-step", icon: KeyRound },
  resend: { label: "Resend invitation", icon: Send },
  cancel: { label: "Cancel invitation", icon: X, destructive: true },
};

type Open =
  | { kind: "invite" }
  | { kind: "employee"; user: AccessUser }
  | { kind: "role"; user: AccessUser }
  | {
      kind: "confirm";
      action: "suspend" | "reactivate" | "reset" | "cancel" | "resend";
      user: AccessUser;
    };

/** `/company/users` (plan 8.15): everyone who can sign in, with filters, invitations and row actions. */
export function UserAccessPage({
  list,
  policy,
  matrix,
}: {
  list: AccessList;
  policy: TwoStepPolicy;
  matrix: RoleMatrix;
}) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [open, setOpen] = useState<Open | null>(null);
  const me = useMe();
  const can = useCan();
  const toast = useToast();
  const router = useRouter();
  const viewer = {
    role: me?.role ?? "",
    canInvite: can("rbac.user.invite"),
    canAssign: can("rbac.role.assign"),
  };
  const shown = useMemo(() => filterUsers(list.users, filters), [list.users, filters]);
  const banner = unlinkedBanner(list.unlinked);
  const filtering =
    filters.role !== ALL || filters.status !== ALL || filters.search.trim().length > 0;

  async function resend(user: AccessUser) {
    const outcome = await attempt((api) =>
      api.POST("/users/invitations/{invitation_id}/resend", {
        params: { path: { invitation_id: user.id } },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: `Invitation sent to ${user.email}`, tone: "success" });
      router.refresh();
    } else toast.show({ title: outcome.problem.message, tone: "danger" });
  }

  function choose(action: RowAction, user: AccessUser) {
    if (action === "resend" && (user.role === "company_admin" || user.role === "hr_admin"))
      setOpen({ kind: "confirm", action, user });
    else if (action === "resend") void resend(user);
    else if (action === "role") setOpen({ kind: "role", user });
    else setOpen({ kind: "confirm", action, user });
  }

  const columns = COLUMNS.map((column) =>
    column.id !== "employee" || !viewer.canAssign
      ? column
      : {
          ...column,
          cell: (user: AccessUser) => (
            <div className="flex flex-col items-start gap-1">
              <span>{user.employee_id ? "Linked" : "Not linked"}</span>
              {user.status !== "invited" && (
                <Button
                  variant="plain"
                  size="sm"
                  aria-label={"Link employee for " + fullName(user)}
                  onClick={() => setOpen({ kind: "employee", user })}
                >
                  {user.employee_id ? "Change link" : "Link employee"}
                </Button>
              )}
            </div>
          ),
        },
  );
  const hasRowMenu = list.users.some((u) => rowActions(u, viewer).length > 0);
  const invite = viewer.canInvite ? (
    <Button onClick={() => setOpen({ kind: "invite" })}>Invite user</Button>
  ) : null;

  return (
    <>
      <PageHeader
        title="User access"
        description="Everyone who can sign in to your company, and what they can do."
        actions={
          <div className="flex flex-wrap gap-2">
            <RolesViewer matrix={matrix} />
            {invite}
          </div>
        }
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
            <option value="invited">Invited</option>
          </Select>
        </div>
        <DataTable
          caption="People with access"
          columns={columns}
          rows={shown}
          getRowId={(u) => u.id}
          defaultSort={{ column: "user", direction: "asc" }}
          {...(hasRowMenu
            ? {
                rowMenu: (user: AccessUser) => {
                  const actions = rowActions(user, viewer);
                  return actions.map((action, index) => {
                    const item = ACTION_ITEMS[action];
                    return (
                      <div key={action}>
                        {item.destructive && index > 0 ? <MenuSeparator /> : null}
                        <MenuItem
                          icon={<Icon icon={item.icon} />}
                          destructive={item.destructive ?? false}
                          onSelect={() => choose(action, user)}
                        >
                          {item.label}
                        </MenuItem>
                      </div>
                    );
                  });
                },
              }
            : {})}
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
        <TwoStepPolicyCard policy={policy} mayChange={viewer.canAssign} />
      </div>
      {open?.kind === "invite" ? (
        <InviteSheet
          mayInviteAdmin={viewer.role === "company_admin"}
          onClose={() => setOpen(null)}
        />
      ) : null}
      {open?.kind === "employee" ? (
        <EmployeeLinkSheet user={open.user} onClose={() => setOpen(null)} />
      ) : null}
      {open?.kind === "role" ? (
        <RoleSheet
          user={open.user}
          mayAssignAdmin={viewer.role === "company_admin"}
          onClose={() => setOpen(null)}
        />
      ) : null}
      {open?.kind === "confirm" ? (
        <ConfirmSheet action={open.action} user={open.user} onClose={() => setOpen(null)} />
      ) : null}
    </>
  );
}
