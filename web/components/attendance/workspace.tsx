"use client";

import Link from "next/link";
import { Clock } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { Select } from "@/components/ui/select";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { STATUS, type Attendance, type Person, type Status } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays, addMonths, formatUk, parseIso, startOfWeek, todayIso } from "@/lib/ui/dates";
import { AttendanceExports } from "./exports";
import { RecordSheet } from "./record-sheet";

type Page = components["schemas"]["AttendancePage"];
type Summary = components["schemas"]["AttendanceSummary"];
const SOURCE: Record<string, string> = {
  manual: "Manual",
  import: "Import",
  grid: "Bulk entry",
  clock: "Clock",
  leave_sync: "Approved leave",
};
type Range = "day" | "week" | "month" | "custom";

export function AttendanceWorkspace({
  employeeId,
  initialMonth,
  profile = false,
}: {
  employeeId?: string;
  initialMonth?: string;
  profile?: boolean;
}) {
  const can = useCan();
  const [on, setOn] = useState(() =>
    initialMonth && parseIso(initialMonth + "-01") ? initialMonth + "-01" : todayIso(),
  );
  const [range, setRange] = useState<Range>(profile || initialMonth ? "month" : "day");
  const [customEnd, setCustomEnd] = useState(on);
  const [employee, setEmployee] = useState(employeeId ?? "");
  const [status, setStatus] = useState<Status | "all">("all");
  const [people, setPeople] = useState<Person[]>([]);
  const [page, setPage] = useState<Page | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [dataKey, setDataKey] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Attendance | "new" | null>(null);
  const [version, setVersion] = useState(0);
  const mayWrite = can("attendance.record.write");
  const mayFilterPeople = can("employee.profile.read", "employee.profile.read_reports");
  const own = !can("attendance.record.read") && can("attendance.record.read_own");
  const selectedEmployee = own ? undefined : profile ? employeeId : employee;
  const dates = useMemo(() => {
    if (range === "week") {
      const start = startOfWeek(on);
      return { start, end: addDays(start, 6) };
    }
    if (range === "month") {
      const start = on.slice(0, 7) + "-01";
      return { start, end: addDays(addMonths(start, 1), -1) };
    }
    return { start: on, end: range === "custom" ? customEnd : on };
  }, [on, range, customEnd]);
  const key = JSON.stringify([dates, selectedEmployee, status, own, profile, version]);
  useEffect(() => {
    let active = true;
    if (mayFilterPeople || mayWrite)
      void attempt((c) => c.GET("/employees")).then((result) => {
        if (!active) return;
        if (result.ok) setPeople(result.data.employees);
        else setProblem(result.problem);
      });
    return () => {
      active = false;
    };
  }, [mayFilterPeople, mayWrite]);
  useEffect(() => {
    let active = true;
    async function load() {
      const query = {
        ...dates,
        employee_id: selectedEmployee || undefined,
        status: status === "all" ? undefined : status,
      };
      const result = await attempt((c) =>
        own
          ? c.GET("/attendance-records/own", { params: { query } })
          : c.GET("/attendance-records", { params: { query } }),
      );
      if (!active) return;
      if (result.ok) {
        setPage(result.data);
        setProblem(null);
      } else {
        setPage(null);
        setProblem(result.problem);
      }
      setSummary(null);
      setDataKey(key);
      if (!profile) {
        const counts = await attempt((c) =>
          c.GET("/attendance-records/summary", {
            params: { query: { on, employee_id: selectedEmployee || undefined } },
          }),
        );
        if (!active) return;
        if (counts.ok) setSummary(counts.data);
        else {
          setSummary(null);
          setProblem(counts.problem);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [dates, selectedEmployee, status, own, profile, key, on]);
  async function more() {
    if (!page || page.next_offset === null) return;
    setBusy(true);
    const query = {
      ...dates,
      employee_id: selectedEmployee || undefined,
      status: status === "all" ? undefined : status,
      offset: page.next_offset,
    };
    const result = await attempt((c) =>
      own
        ? c.GET("/attendance-records/own", { params: { query } })
        : c.GET("/attendance-records", { params: { query } }),
    );
    setBusy(false);
    if (result.ok) setPage({ ...result.data, items: [...page.items, ...result.data.items] });
    else setProblem(result.problem);
  }
  const rows = dataKey === key ? (page?.items ?? []) : [];
  const columns: Column<Attendance>[] = [
    ...(!profile
      ? [
          {
            id: "employee",
            header: "Employee",
            primary: true,
            cell: (r: Attendance) => r.employee_name,
            sortValue: (r: Attendance) => r.employee_name,
          },
        ]
      : []),
    {
      id: "date",
      header: "Date",
      primary: profile,
      cell: (r) => formatUk(r.date),
      sortValue: (r) => r.date,
    },
    {
      id: "status",
      header: "Status",
      cell: (r) => (
        <StatusChip
          tone={
            r.status === "present"
              ? "success"
              : r.status === "late" || r.status === "absent"
                ? "warning"
                : "info"
          }
        >
          {STATUS[r.status]}
        </StatusChip>
      ),
    },
    { id: "in", header: "Clock in", cell: (r) => r.clock_in_local ?? "—" },
    { id: "out", header: "Clock out", cell: (r) => r.clock_out_local ?? "—" },
    { id: "break", header: "Break (min)", cell: (r) => r.unpaid_break_minutes },
    {
      id: "hours",
      header: "Hours",
      cell: (r) =>
        r.hours === null
          ? "—"
          : Number(r.hours).toLocaleString("en-GB", { maximumFractionDigits: 2 }),
    },
    {
      id: "note",
      header: "Note",
      cell: (r) => <span className="block max-w-xs truncate">{r.note || "—"}</span>,
    },
    { id: "source", header: "Source", cell: (r) => SOURCE[r.source] ?? r.source },
    {
      id: "view",
      header: "Record",
      cell: (r) => (
        <Button size="sm" variant="gray" onClick={() => setEditing(r)}>
          {mayWrite && r.source !== "leave_sync" ? "Edit record" : "View record"}
        </Button>
      ),
    },
  ];
  const content = (
    <section
      aria-label={profile ? "Attendance history" : "Attendance workspace"}
      className="flex flex-col gap-5"
    >
      {profile && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-title-3 text-label">Attendance history</h2>
          {mayWrite && (
            <Button variant="gray" onClick={() => setEditing("new")}>
              Record attendance
            </Button>
          )}
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3">
        {profile ? (
          <TextField
            label="Month"
            type="month"
            value={on.slice(0, 7)}
            onChange={(e) => {
              if (e.target.value) setOn(e.target.value + "-01");
            }}
          />
        ) : (
          <>
            <SegmentedControl
              label="Attendance range"
              value={range}
              onValueChange={setRange}
              segments={[
                { value: "day", label: "Day" },
                { value: "week", label: "Week" },
                { value: "month", label: "Month" },
                { value: "custom", label: "Custom" },
              ]}
            />
            <TextField
              label={range === "custom" ? "Start date" : "Selected day"}
              type="date"
              value={on}
              onChange={(e) => {
                if (parseIso(e.target.value)) setOn(e.target.value);
              }}
            />
            {range === "custom" && (
              <TextField
                label="End date"
                type="date"
                min={on}
                value={customEnd}
                onChange={(e) => {
                  if (parseIso(e.target.value)) setCustomEnd(e.target.value);
                }}
              />
            )}
            {mayFilterPeople && (
              <Select
                label="Employee"
                value={employee}
                onChange={(e) => setEmployee(e.target.value)}
              >
                <option value="">All employees</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name} · {p.employee_number}
                  </option>
                ))}
              </Select>
            )}
          </>
        )}
        <Select
          label="Attendance status"
          value={status}
          onChange={(e) => setStatus(e.target.value as Status | "all")}
        >
          <option value="all">All statuses</option>
          {Object.entries(STATUS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      {!profile && (
        <div className="flex flex-wrap items-center gap-2" aria-label="Attendance tools">
          {mayWrite && (
            <>
              <Button asChild variant="gray">
                <Link href="/attendance/import">Import</Link>
              </Button>
              <Button asChild variant="gray">
                <Link href="/attendance/bulk">Bulk entry</Link>
              </Button>
            </>
          )}
          <AttendanceExports
            start={dates.start}
            end={dates.end}
            employeeId={selectedEmployee || undefined}
            status={status === "all" ? undefined : status}
          />
          <Button asChild variant="gray">
            <Link href={`/attendance/absences?month=${on.slice(0, 7)}`}>Absences this month</Link>
          </Button>
        </div>
      )}
      {problem && <Alert tone="danger" title={problem.message} />}
      {!profile && summary && dataKey === key && (
        <div>
          <h2 className="text-headline text-label mb-3">
            {formatUk(on)} · {summary.timezone}
          </h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
            <KpiCard label="Employees" value={summary.employees} />
            <KpiCard label="Present" value={summary.counts.present ?? 0} />
            <KpiCard label="Absent" value={summary.counts.absent ?? 0} />
            <KpiCard label="Late" value={summary.counts.late ?? 0} />
            <KpiCard label="Half day" value={summary.counts.half_day ?? 0} />
            <KpiCard
              label="On leave / Sick"
              value={(summary.counts.on_leave ?? 0) + (summary.counts.sick ?? 0)}
            />
          </div>
          <p className="text-caption text-label-secondary mt-3">
            {summary.not_recorded} employees without a record for this day.
          </p>
        </div>
      )}
      <p className="text-caption text-label-secondary">
        {formatUk(dates.start)} to {formatUk(dates.end)} · Times in{" "}
        {page?.timezone ?? "the company time zone"}. Overnight shifts belong to their start date.
      </p>
      <DataTable
        caption="Attendance records"
        rows={rows}
        columns={columns}
        getRowId={(r) => r.id}
        loading={dataKey !== key}
        onRowOpen={setEditing}
        empty={
          <EmptyState
            icon={Clock}
            title="No attendance recorded"
            description="Choose another date range or record attendance for this period."
          />
        }
      />
      {dataKey === key && page?.next_offset !== null && page?.next_offset !== undefined && (
        <Button loading={busy} variant="gray" onClick={() => void more()}>
          Load more records
        </Button>
      )}
      <Sheet
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
      >
        {editing &&
          (editing !== "new" &&
          (!mayWrite || editing.source === "leave_sync" || editing.leave_request_id) ? (
            <SheetContent
              title="Attendance record"
              description={`${editing.employee_name} · ${formatUk(editing.date)}`}
              readOnly
            >
              <div className="flex flex-col gap-4">
                <p>
                  {STATUS[editing.status]} · {SOURCE[editing.source] ?? editing.source}
                </p>
                {editing.source === "leave_sync" && (
                  <Alert title="This record comes from approved leave and is protected from manual edits." />
                )}
                <p>
                  {editing.clock_in_local ?? "—"} to {editing.clock_out_local ?? "—"} ·{" "}
                  {editing.hours ?? "—"} hours
                </p>
                <p className="whitespace-pre-wrap break-words">
                  {editing.note || "No note recorded."}
                </p>
              </div>
            </SheetContent>
          ) : (
            <RecordSheet
              key={editing === "new" ? "new" : editing.id}
              row={editing === "new" ? null : editing}
              people={people}
              employeeId={selectedEmployee || undefined}
              on={on}
              timezone={page?.timezone ?? summary?.timezone ?? "Europe/London"}
              saved={() => {
                setEditing(null);
                setVersion((v) => v + 1);
              }}
            />
          ))}
      </Sheet>
    </section>
  );
  return profile ? (
    content
  ) : (
    <>
      <PageHeader
        title="Attendance"
        description="Records, hours and absences across your team."
        actions={
          mayWrite ? <Button onClick={() => setEditing("new")}>Record attendance</Button> : null
        }
      />
      {content}
    </>
  );
}
