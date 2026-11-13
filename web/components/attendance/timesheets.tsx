"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { DatePicker } from "@/components/ui/date-picker";
import type { components } from "@/lib/api/client";
import { STATUS } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays, formatUk, startOfWeek, todayIso } from "@/lib/ui/dates";

type Page = components["schemas"]["TimesheetPage"];
type Timesheet = components["schemas"]["TimesheetOut"];

export function AttendanceTimesheets() {
  const can = useCan();
  const permitted = can("attendance.timesheet.approve", "attendance.timesheet.approve_reports");
  const [start, setStart] = useState(() => addDays(startOfWeek(todayIso()), -7));
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [opened, setOpened] = useState<Timesheet | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [loaded, setLoaded] = useState("");
  const key = `${start}:${offset}:${version}`;
  useEffect(() => {
    if (!permitted) return;
    let active = true;
    void attempt((c) =>
      c.GET("/attendance/timesheets", { params: { query: { start, offset } } }),
    ).then((result) => {
      if (!active) return;
      setLoaded(key);
      if (result.ok) {
        setPage(result.data);
        setProblem(null);
      } else {
        setPage(null);
        setProblem(result.problem);
      }
    });
    return () => {
      active = false;
    };
  }, [start, offset, version, key, permitted]);
  async function approve() {
    if (!opened) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/attendance/timesheets/{timesheet_id}/approve", {
        params: { path: { timesheet_id: opened.id } },
        body: {
          employee_id: opened.employee_id,
          period_start: opened.period_start,
          fingerprint: opened.fingerprint,
        },
      }),
    );
    setBusy(false);
    if (result.ok) {
      setOpened(result.data);
      setVersion((v) => v + 1);
    } else setProblem(result.problem);
  }
  function state(row: Timesheet) {
    return row.approved_at ? "Approved" : row.incomplete ? "Incomplete" : "Needs review";
  }
  const columns: Column<Timesheet>[] = [
    { id: "employee", header: "Employee", primary: true, cell: (r) => r.employee_name },
    { id: "hours", header: "Hours", cell: (r) => r.hours },
    { id: "records", header: "Days recorded", cell: (r) => r.records.length },
    { id: "status", header: "Status", cell: state },
    {
      id: "review",
      header: "Review",
      cell: (r) => (
        <Button variant="gray" size="sm" onClick={() => setOpened(r)}>
          Review {r.employee_name}
        </Button>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Timesheet approvals"
        description="Review weekly attendance for your direct and indirect reports."
        actions={
          <Button asChild variant="gray">
            <Link href="/attendance">Attendance</Link>
          </Button>
        }
      />
      {!permitted ? (
        <Alert title="You do not have permission to approve timesheets." />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-end gap-3">
            <DatePicker
              label="Timesheet week containing"
              value={start || null}
              onChange={(picked) => {
                if (picked ?? "") {
                  setStart(startOfWeek(picked ?? ""));
                  setOffset(0);
                }
              }}
            />
            <Button variant="gray" onClick={() => setVersion((v) => v + 1)}>
              Reload timesheets
            </Button>
          </div>
          <p className="text-callout text-label-secondary">
            Weeks run Monday to Sunday. Approve after the week ends and clock times are complete.
            Changed attendance needs review again. You cannot approve your own time.
          </p>
          {problem && !opened && <Alert tone="danger" title={problem.message} />}
          <DataTable
            caption="Report timesheets"
            rows={loaded === key ? (page?.items ?? []) : []}
            loading={loaded !== key}
            columns={columns}
            getRowId={(r) => r.id}
            onRowOpen={setOpened}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="gray"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              Previous reports
            </Button>
            <Button
              variant="gray"
              disabled={loaded !== key || page?.next_offset == null}
              onClick={() => setOffset(page?.next_offset ?? 0)}
            >
              Next reports
            </Button>
          </div>
        </div>
      )}
      <Sheet
        open={opened !== null}
        onOpenChange={(open) => {
          if (!open && !busy) {
            setOpened(null);
            setProblem(null);
          }
        }}
      >
        {opened && (
          <SheetContent title={`${opened.employee_name} timesheet`} readOnly>
            <div className="flex flex-col gap-4">
              <p>
                {formatUk(opened.period_start)} to {formatUk(opened.period_end)} · {opened.hours}{" "}
                hours
              </p>
              {problem && (
                <Alert tone="danger" title={problem.message}>
                  <Button
                    variant="gray"
                    onClick={() => {
                      setOpened(null);
                      setVersion((v) => v + 1);
                    }}
                  >
                    Reload for review
                  </Button>
                </Alert>
              )}
              <p className="text-headline">{state(opened)}</p>
              {opened.approved_at && (
                <p>Approved {new Date(opened.approved_at).toLocaleString("en-GB")}</p>
              )}
              <ul className="flex flex-col gap-3" aria-label="Timesheet records">
                {opened.records.map((r) => (
                  <li key={r.id} className="border-separator rounded-control border p-3">
                    <p className="font-medium">
                      {formatUk(r.date)} · {STATUS[r.status]}
                    </p>
                    <p>
                      {r.clock_in_local ?? "—"} to {r.clock_out_local ?? "—"} ·{" "}
                      {r.hours ?? "Unknown"} hours · {r.unpaid_break_minutes} minute break
                    </p>
                    <p className="text-caption text-label-secondary">
                      Source: {r.source.replaceAll("_", " ")}
                    </p>
                    {r.note && <p className="whitespace-pre-wrap break-words">{r.note}</p>}
                  </li>
                ))}
              </ul>
              {!opened.approved_at && (
                <InlineConfirm
                  label="Approve timesheet"
                  prompt="Approve these reviewed attendance records?"
                  confirmLabel="Confirm approval"
                  disabled={busy || opened.incomplete}
                  onConfirm={approve}
                />
              )}
            </div>
          </SheetContent>
        )}
      </Sheet>
    </>
  );
}
