"use client";

import { Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { useNewShortcut } from "@/components/app/shortcut-provider";
import { RTWChip } from "@/components/employees/rtw-chip";
import { RTW_FILTERS, RTW_LABEL, type RTWFilter } from "@/lib/employees/rtw";
import { Button } from "@/components/ui/button";
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
        <Avatar
          name={name(e)}
          size="sm"
          decorative
          src={
            e.has_photo
              ? `${process.env.NEXT_PUBLIC_API_URL ?? ""}/employees/${e.id}/photo`
              : undefined
          }
        />
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
    id: "rtw",
    header: "Right to Work",
    sortValue: (e) => RTW_LABEL[e.rtw_status ?? "not_recorded"],
    exportValue: (e) => RTW_LABEL[e.rtw_status ?? "not_recorded"],
    cell: (e) => <RTWChip status={e.rtw_status} />,
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
  initialRtw = "all",
}: {
  employees: EmployeeRow[];
  summary: EmployeeSummary;
  archived: boolean;
  initialPill: PillId;
  initialRtw?: RTWFilter;
}) {
  const router = useRouter();
  const mayAdd = useCan()("employee.profile.write");
  const addEmployee = useCallback(() => {
    if (mayAdd) router.push("/employees/new");
  }, [mayAdd, router]);
  useNewShortcut(addEmployee);
  const [pill, setPill] = useState<PillId>(initialPill);
  const [rtw, setRtw] = useState<RTWFilter>(initialRtw);
  const [department, setDepartment] = useState(ALL_DEPARTMENTS);
  const [search, setSearch] = useState("");
  const shown = useMemo(
    () => filterEmployees(employees, { pill: archived ? "all" : pill, department, search, rtw }),
    [employees, pill, department, search, archived, rtw],
  );
  const departments = useMemo(() => departmentsIn(employees), [employees]);
  const filtering =
    rtw !== "all" ||
    search.trim() !== "" ||
    department !== ALL_DEPARTMENTS ||
    (!archived && pill !== "all");

  return (
    <>
      <PageHeader
        actions={mayAdd ? <Button onClick={addEmployee}>New employee</Button> : null}
        title={archived ? "Archived employees" : "Employees"}
        description={
          archived
            ? "Records that have been put away. They are kept, not deleted."
            : summaryLine(summary)
        }
      />
      <div className="flex flex-col gap-4">
        {archived ? null : (
          <div className="max-w-full overflow-x-auto">
            <SegmentedControl<PillId>
              className="min-w-max"
              label="Show"
              value={pill}
              onValueChange={setPill}
              segments={PILLS.map((p) => ({ value: p.id, label: p.label }))}
            />
          </div>
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
          <Select
            label="Right to Work"
            value={rtw}
            onChange={(e) => setRtw(e.target.value as RTWFilter)}
          >
            {RTW_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
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
          onRowOpen={(e) => router.push(`/employees/${e.id}`)}
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
                    : mayAdd
                      ? "Add your first employee to get started."
                      : "Employees you add will appear here."
              }
            />
          }
        />
      </div>
    </>
  );
}
