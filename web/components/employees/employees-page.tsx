"use client";

import { Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Avatar } from "@/components/ui/avatar";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { Toggle } from "@/components/ui/toggle";
import {
  ALL_DEPARTMENTS,
  departmentsIn,
  filterEmployees,
  PILLS,
  STATUS_LABEL,
  summaryLine,
  type EmployeeRow,
  type EmployeeSummary,
  type PillId,
} from "@/lib/employees/list";

const TONE = {
  active: "success",
  on_leave: "info",
  leaver: "neutral",
  archived: "neutral",
} as const;

const name = (e: EmployeeRow) => `${e.first_name} ${e.last_name}`;

const COLUMNS: Column<EmployeeRow>[] = [
  {
    id: "employee",
    header: "Employee",
    primary: true,
    sortValue: (e) => `${e.last_name} ${e.first_name}`.toLowerCase(),
    exportValue: (e) => `${name(e)} (${e.employee_number})`,
    cell: (e) => (
      <div className="flex items-center gap-3">
        <Avatar name={name(e)} size="sm" decorative />
        <div className="min-w-0">
          <p className="text-body text-label truncate">{name(e)}</p>
          <p className="text-footnote text-secondary-label truncate">{e.employee_number}</p>
        </div>
      </div>
    ),
  },
  {
    id: "department",
    header: "Department",
    sortValue: (e) => e.department,
    cell: (e) => e.department ?? <span className="text-secondary-label">Not set</span>,
  },
  {
    id: "designation",
    header: "Designation",
    sortValue: (e) => e.designation,
    cell: (e) => e.designation ?? <span className="text-secondary-label">Not set</span>,
  },
  {
    id: "status",
    header: "Status",
    sortValue: (e) => e.status,
    cell: (e) => <StatusChip tone={TONE[e.status]}>{STATUS_LABEL[e.status]}</StatusChip>,
  },
];

/** `/employees` and `/employees/archived` (plan 8.3): pills, search, department filter, summary. */
export function EmployeesPage({
  employees,
  summary,
  archived,
  initialPill,
}: {
  employees: EmployeeRow[];
  summary: EmployeeSummary;
  archived: boolean;
  initialPill: PillId;
}) {
  const router = useRouter();
  const [pill, setPill] = useState<PillId>(initialPill);
  const [department, setDepartment] = useState(ALL_DEPARTMENTS);
  const [search, setSearch] = useState("");
  const shown = useMemo(
    () => filterEmployees(employees, { pill: archived ? "all" : pill, department, search }),
    [employees, pill, department, search, archived],
  );
  const departments = useMemo(() => departmentsIn(employees), [employees]);
  const filtering =
    search.trim() !== "" || department !== ALL_DEPARTMENTS || (!archived && pill !== "all");

  return (
    <>
      <PageHeader
        title={archived ? "Archived employees" : "Employees"}
        description={
          archived
            ? "Records that have been put away. They are kept, not deleted."
            : summaryLine(summary)
        }
      />
      <div className="flex flex-col gap-4">
        {archived ? null : (
          <SegmentedControl<PillId>
            label="Show"
            value={pill}
            onValueChange={setPill}
            segments={PILLS.map((p) => ({ value: p.id, label: p.label }))}
          />
        )}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <SearchField
            label="Search by name or number"
            listSearch
            containerClassName="sm:w-72"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {departments.length > 0 ? (
            <Select
              label="Department"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              <option value={ALL_DEPARTMENTS}>All departments</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </Select>
          ) : null}
          <Toggle
            label="Show archived"
            checked={archived}
            onCheckedChange={(on) => router.push(on ? "/employees/archived" : "/employees")}
          />
        </div>
        <DataTable
          caption={archived ? "Archived employees" : "Employees"}
          columns={COLUMNS}
          rows={shown}
          getRowId={(e) => e.id}
          defaultSort={{ column: "employee", direction: "asc" }}
          empty={
            <EmptyState
              icon={Users}
              title={
                filtering
                  ? "Nobody matches"
                  : archived
                    ? "No archived employees"
                    : "No employees yet"
              }
              description={
                filtering
                  ? "Try a different search or clear the filters."
                  : archived
                    ? "Records you archive will be kept here."
                    : "Employees you add will appear here."
              }
            />
          }
        />
      </div>
    </>
  );
}
