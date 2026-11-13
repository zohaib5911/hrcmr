"use client";

import { ScrollText } from "lucide-react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/text-field";
import { Select } from "@/components/ui/select";
import { type components } from "@/lib/api/client";
import { baseUrl } from "@/lib/auth/request";
import { PAGE_SIZE, queryString, type AuditFilters } from "@/lib/platform/operations";
import { formatUk } from "@/lib/ui/dates";

type AuditRow = components["schemas"]["AuditLogOut"]["items"][number];

const COLUMNS: readonly Column<AuditRow>[] = [
  { id: "date", header: "Date", cell: (row) => formatUk(row.created_at.slice(0, 10)) },
  { id: "actor", header: "Actor", cell: (row) => row.actor },
  {
    id: "action",
    header: "Action",
    primary: true,
    cell: (row) => <span className="break-words">{row.action}</span>,
  },
  {
    id: "summary",
    header: "Summary",
    cell: (row) => <span className="break-words">{row.summary ?? "–"}</span>,
  },
  {
    id: "reason",
    header: "Reason",
    cell: (row) => <span className="break-words">{row.reason ?? "–"}</span>,
  },
];

const pageLink = buttonVariants({ variant: "gray", size: "sm" });

export function AuditAdmin({
  data,
  filters,
  offset,
}: {
  data: components["schemas"]["AuditLogOut"] | null;
  filters: AuditFilters;
  offset: number;
}) {
  return (
    <>
      <PageHeader
        title="Platform audit log"
        description="Platform actions and system jobs. A trailing dot in the action matches a family, for example platform."
        actions={
          <a
            className={buttonVariants({ variant: "gray" })}
            href={`${baseUrl()}/platform/audit/export?${queryString(filters)}`}
          >
            Export CSV
          </a>
        }
      />
      <form action="/audit" method="get" className="mb-6 grid items-end gap-4 sm:grid-cols-2">
        <TextField
          label="Action family"
          name="action"
          defaultValue={filters.action ?? ""}
          maxLength={100}
          clearable={false}
        />
        <Select label="Actor" name="actor_type" defaultValue={filters.actor_type ?? ""}>
          <option value="">All actors</option>
          <option value="platform_admin">Platform admin</option>
          <option value="system">System</option>
        </Select>
        <TextField
          label="From date (UTC)"
          type="date"
          name="since"
          defaultValue={filters.since?.slice(0, 10) ?? ""}
          clearable={false}
        />
        <TextField
          label="To date (UTC)"
          type="date"
          name="until"
          defaultValue={filters.until?.slice(0, 10) ?? ""}
          clearable={false}
        />
        <Button type="submit" className="self-end justify-self-start">
          Apply filters
        </Button>
      </form>
      {!data ? (
        <Alert tone="danger" title="Could not load audit log">
          Reload to try again.
        </Alert>
      ) : (
        <DataTable
          caption="Platform audit events"
          columns={COLUMNS}
          rows={data.items}
          getRowId={(row) => row.id}
          pageSize={PAGE_SIZE}
          pager={false}
          empty={
            <EmptyState
              icon={ScrollText}
              title="No audit events"
              description="No audit events match these filters."
            />
          }
        />
      )}
      <nav aria-label="Audit pages" className="mt-4 flex gap-3">
        {offset > 0 && (
          <a
            className={pageLink}
            href={`/audit?${queryString({ ...filters, offset: Math.max(0, offset - PAGE_SIZE) })}`}
          >
            Previous
          </a>
        )}
        {data && offset + PAGE_SIZE < data.total && (
          <a
            className={pageLink}
            href={`/audit?${queryString({ ...filters, offset: offset + PAGE_SIZE })}`}
          >
            Next
          </a>
        )}
      </nav>
    </>
  );
}
