"use client";

import { BadgeCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { RTWChip } from "@/components/employees/rtw-chip";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { Select } from "@/components/ui/select";
import type { components } from "@/lib/api/schema";
import { VISA_ROUTES, routeLabel } from "@/lib/compliance/sponsor-documents";
import { shortDate } from "@/lib/employees/profile";
import { RTW_LABEL } from "@/lib/employees/rtw";

type Employee = components["schemas"]["SponsoredEmployee"];
const COLUMNS: Column<Employee>[] = [
  {
    id: "employee",
    header: "Employee",
    primary: true,
    sortValue: (e) => (e.last_name + " " + e.first_name).toLowerCase(),
    exportValue: (e) => e.first_name + " " + e.last_name + " (" + e.employee_number + ")",
    cell: (e) => (
      <div className="min-w-0">
        <p className="text-body text-label truncate">
          {e.first_name} {e.last_name}
        </p>
        <p className="text-footnote text-label-secondary">{e.employee_number}</p>
      </div>
    ),
  },
  {
    id: "route",
    header: "Visa route",
    sortValue: (e) => routeLabel(e.visa_route),
    cell: (e) => routeLabel(e.visa_route),
  },
  {
    id: "cos",
    header: "CoS (masked)",
    sortValue: (e) => e.cos_number_masked,
    cell: (e) => e.cos_number_masked ?? "Not set",
  },
  {
    id: "soc",
    header: "SOC code",
    sortValue: (e) => e.soc_code,
    cell: (e) => e.soc_code ?? "Not set",
  },
  {
    id: "expiry",
    header: "Visa expiry",
    sortValue: (e) => e.expiry_date,
    cell: (e) => (e.expiry_date ? shortDate(e.expiry_date) : "Not set"),
  },
  {
    id: "rtw",
    header: "Right to Work",
    sortValue: (e) => RTW_LABEL[e.rtw_status],
    exportValue: (e) => RTW_LABEL[e.rtw_status],
    cell: (e) => <RTWChip status={e.rtw_status} />,
  },
];

export function SponsoredEmployeesPage({ employees }: { employees: Employee[] }) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [route, setRoute] = useState("all");
  const shown = useMemo(() => {
    const words = search.toLowerCase().split(/\s+/).filter(Boolean);
    return employees.filter(
      (e) =>
        (route === "all" || e.visa_route === route) &&
        words.every((w) =>
          (e.first_name + " " + e.last_name + " " + e.employee_number + " " + (e.soc_code ?? ""))
            .toLowerCase()
            .includes(w),
        ),
    );
  }, [employees, search, route]);
  const filtering = search.trim() !== "" || route !== "all";
  return (
    <>
      <PageHeader
        title="Sponsored employees"
        description={`${employees.length} ${employees.length === 1 ? "employee" : "employees"} with a current sponsored-route visa record.`}
      />
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <SearchField
            label="Search by name, number or SOC code"
            listSearch
            containerClassName="sm:w-80"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Select label="Visa route" value={route} onChange={(e) => setRoute(e.target.value)}>
            <option value="all">All sponsored routes</option>
            {VISA_ROUTES.slice(0, 5).map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          caption="Sponsored employees"
          columns={COLUMNS}
          rows={shown}
          getRowId={(e) => e.id}
          onRowOpen={(e) => router.push("/employees/" + e.id)}
          defaultSort={{ column: "employee", direction: "asc" }}
          empty={
            <EmptyState
              icon={BadgeCheck}
              title={filtering ? "Nobody matches" : "No sponsored employees yet"}
              description={
                filtering
                  ? "Try a different search or clear the route filter."
                  : "Add a sponsored-route visa to an employee's Sponsor compliance tab to include them here."
              }
            />
          }
        />
      </div>
    </>
  );
}
