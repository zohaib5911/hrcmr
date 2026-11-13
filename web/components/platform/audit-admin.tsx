"use client";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { Select } from "@/components/ui/select";
import { type components } from "@/lib/api/client";
import { baseUrl } from "@/lib/auth/request";
import { PAGE_SIZE, queryString, type AuditFilters } from "@/lib/platform/operations";
import { formatUk } from "@/lib/ui/dates";

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
      />
      <form action="/audit" method="get" className="mb-6 grid gap-4 sm:grid-cols-2">
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
        <Button type="submit">Apply filters</Button>
      </form>
      <a
        className="text-accent-text underline"
        href={`${baseUrl()}/platform/audit/export?${queryString(filters)}`}
      >
        Export CSV
      </a>
      {!data ? (
        <Alert tone="danger" title="Could not load audit log">
          Reload to try again.
        </Alert>
      ) : data.items.length === 0 ? (
        <p className="mt-6">No audit events match these filters.</p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-callout">
            <caption className="sr-only">Platform audit events</caption>
            <thead>
              <tr>
                {["Date", "Actor", "Action", "Summary", "Reason"].map((h) => (
                  <th key={h} className="p-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id} className="border-t border-separator">
                  {[
                    formatUk(row.created_at.slice(0, 10)),
                    row.actor,
                    row.action,
                    row.summary ?? "–",
                    row.reason ?? "–",
                  ].map((value, i) => (
                    <td key={i} className="p-2 break-words">
                      {value}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <nav aria-label="Audit pages" className="mt-6 flex gap-4">
        {offset > 0 && (
          <a
            href={`/audit?${queryString({ ...filters, offset: Math.max(0, offset - PAGE_SIZE) })}`}
          >
            Previous
          </a>
        )}
        {data && offset + PAGE_SIZE < data.total && (
          <a href={`/audit?${queryString({ ...filters, offset: offset + PAGE_SIZE })}`}>Next</a>
        )}
      </nav>
    </>
  );
}
