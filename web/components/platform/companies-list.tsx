"use client";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { formatUk } from "@/lib/ui/dates";

export type CompanyFilters = {
  q?: string;
  plan?: string;
  status?: string;
  created_since?: string;
  active_since?: string;
  offset: number;
};
export function CompaniesList({
  data,
  filters,
}: {
  data: components["schemas"]["CompaniesOut"] | null;
  filters: CompanyFilters;
}) {
  const link = (offset: number) => {
    const query = new URLSearchParams();
    Object.entries({ ...filters, offset }).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return `/companies?${query}`;
  };
  return (
    <div className="mx-auto grid max-w-6xl gap-6">
      <PageHeader
        title="Companies"
        description="Search companies and review their access and platform actions."
      />
      <form action="/companies" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <TextField label="Search companies" name="q" defaultValue={filters.q} maxLength={120} />
        <Select label="Plan" name="plan" defaultValue={filters.plan ?? ""}>
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="annual">Annual</option>
          <option value="ten_year">Ten year</option>
        </Select>
        <Select label="Status" name="status" defaultValue={filters.status ?? ""}>
          <option value="">All statuses</option>
          {["active", "suspended", "pending_deletion", "deleted"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <TextField
          label="Created since"
          name="created_since"
          type="date"
          defaultValue={filters.created_since?.slice(0, 10)}
        />
        <TextField
          label="Active since"
          name="active_since"
          type="date"
          defaultValue={filters.active_since?.slice(0, 10)}
        />
        <Button type="submit">Search</Button>
      </form>
      {!data ? (
        <Alert tone="danger" title="Companies could not be loaded">
          Try reloading this page.
        </Alert>
      ) : (
        <>
          <p>{data.total} companies</p>
          {data.items.length ? (
            <ul className="grid gap-3">
              {data.items.map((c) => (
                <li key={c.id}>
                  <Card>
                    <CardBody className="flex flex-wrap items-center justify-between gap-3 py-4">
                      <div className="min-w-0 break-words">
                        <a className="text-accent font-medium" href={`/companies/${c.id}`}>
                          {c.name}
                        </a>
                        <p>{c.contact_email ?? c.slug}</p>
                        <p className="text-footnote text-label-secondary">
                          {c.plan} · {c.members} people · Created{" "}
                          {formatUk(c.created_at.slice(0, 10))}
                        </p>
                      </div>
                      <StatusChip tone={c.status === "active" ? "success" : "warning"}>
                        {c.status}
                      </StatusChip>
                    </CardBody>
                  </Card>
                </li>
              ))}
            </ul>
          ) : (
            <p>No companies match these filters.</p>
          )}
          <nav aria-label="Company pages" className="flex flex-wrap gap-4">
            {filters.offset > 0 ? (
              <a href={link(Math.max(0, filters.offset - 25))} className="text-accent">
                Previous
              </a>
            ) : null}
            {filters.offset + 25 < data.total ? (
              <a href={link(filters.offset + 25)} className="text-accent">
                Next
              </a>
            ) : null}
          </nav>
        </>
      )}
    </div>
  );
}
