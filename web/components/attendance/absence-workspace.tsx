"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { KpiCard } from "@/components/ui/kpi-card";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { STATUS, type Attendance } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays, addMonths, formatUk, parseIso, todayIso } from "@/lib/ui/dates";
import { AttendanceExports } from "./exports";
type Report = components["schemas"]["AbsenceOut"];
export function AttendanceAbsences({ initialMonth }: { initialMonth?: string }) {
  const [month, setMonth] = useState(() =>
    initialMonth && parseIso(initialMonth + "-01") ? initialMonth : todayIso().slice(0, 7),
  );
  const [report, setReport] = useState<Report | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/attendance/absences", { params: { query: { month } } })).then(
      (result) => {
        if (!active) return;
        if (result.ok) {
          setReport(result.data);
          setProblem(null);
        } else {
          setReport(null);
          setProblem(result.problem);
        }
      },
    );
    return () => {
      active = false;
    };
  }, [month]);
  const columns: Column<Attendance>[] = [
    {
      id: "employee",
      header: "Employee",
      primary: true,
      cell: (r) => r.employee_name,
      sortValue: (r) => r.employee_name,
    },
    { id: "date", header: "Date", cell: (r) => formatUk(r.date), sortValue: (r) => r.date },
    { id: "status", header: "Status", cell: (r) => STATUS[r.status] },
    { id: "days", header: "Days", cell: (r) => (r.status === "half_day" ? "0.5" : "1") },
    {
      id: "note",
      header: "Note",
      cell: (r) => (
        <span className="block max-w-xs whitespace-pre-wrap break-words">{r.note || "—"}</span>
      ),
    },
  ];
  const current = report?.month === month ? report : null;
  return (
    <>
      <PageHeader
        title="Absences this month"
        description="Recorded absence, sickness, leave and half days."
        actions={
          <Button asChild variant="gray">
            <Link href="/attendance">Attendance</Link>
          </Button>
        }
      />
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-end gap-3">
          <TextField
            label="Absence month"
            type="month"
            value={month}
            onChange={(e) => {
              if (e.target.value) setMonth(e.target.value);
            }}
          />
          <AttendanceExports
            start={month + "-01"}
            end={addDays(addMonths(month + "-01", 1), -1)}
            absencesOnly
          />
        </div>
        {problem && <Alert tone="danger" title={problem.message} />}
        {current && (
          <div className="grid grid-cols-2 gap-3">
            <KpiCard label="Absence days" value={Number(current.days)} />
            <KpiCard label="Employees affected" value={current.employees} />
          </div>
        )}
        <p className="text-callout text-label-secondary">
          Each recorded absence day counts as one; a half day counts as 0.5. These totals describe
          attendance records and may differ from working-pattern leave balances.
        </p>
        <DataTable
          caption="Monthly absences"
          rows={current?.records ?? []}
          columns={columns}
          getRowId={(r) => r.id}
          loading={!current && !problem}
        />
      </div>
    </>
  );
}
