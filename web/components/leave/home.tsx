"use client";

import { CalendarDays } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { Sheet } from "@/components/ui/sheet";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { monthGrid, todayIso, formatUk, formatUkLong } from "@/lib/ui/dates";
import { COLOUR_CLASS } from "@/lib/company/holidays";
import { BalancePanel, days } from "./balances";
import { RequestSheet, DecisionSheet, type LeaveRequest } from "./request-sheet";

type Mode = "workspace" | "own" | "approvals";
export function LeaveHome({ mode = "workspace" }: { mode?: Mode }) {
  const can = useCan();
  const [view, setView] = useState<"calendar" | "requests" | "balances">(
    can("leave.request.read", "leave.request.read_own") ? "calendar" : "balances",
  );
  const [creating, setCreating] = useState(false);
  const [version, setVersion] = useState(0);
  const mayRead = can("leave.request.read", "leave.request.read_own");
  const mayBalance = can(
    "leave.balance.read",
    "leave.balance.read_own",
    "leave.balance.read_reports",
  );
  const mayCreate =
    mode === "own"
      ? can("leave.request.create_own", "leave.request.create")
      : can("leave.request.create");
  const mayApprove = can("leave.request.approve", "leave.request.approve_reports");
  return (
    <>
      <PageHeader
        title={mode === "own" ? "My Leave" : mode === "approvals" ? "My Approvals" : "Leave"}
        description="Plan time away and review your allowance."
        actions={
          <>
            {mode !== "own" && can("leave.request.read_own", "leave.request.create_own") && (
              <Button asChild variant="gray">
                <Link href="/my-leave">My Leave</Link>
              </Button>
            )}
            {mode !== "approvals" && mayApprove && (
              <Button asChild variant="gray">
                <Link href="/my-approvals">My Approvals</Link>
              </Button>
            )}
            {mode === "workspace" && can("leave.config.read") && (
              <Button asChild variant="gray">
                <Link href="/leave/settings">Leave settings</Link>
              </Button>
            )}
            {mayCreate && (
              <Button onClick={() => setCreating(true)}>
                {mode === "own" ? "Request leave" : "Request on behalf"}
              </Button>
            )}
          </>
        }
      />
      <div className="flex flex-col gap-6">
        {mode === "workspace" && (
          <SegmentedControl
            label="Leave view"
            value={view}
            onValueChange={setView}
            segments={[
              ...(mayRead
                ? [
                    { value: "calendar" as const, label: "Calendar" },
                    { value: "requests" as const, label: "Requests" },
                  ]
                : []),
              ...(mayBalance ? [{ value: "balances" as const, label: "Balances" }] : []),
            ]}
          />
        )}
        {mode === "workspace" && view === "calendar" && mayRead && (
          <LeaveCalendar refresh={version} />
        )}
        {mode === "workspace" && (view === "balances" || !mayRead) && mayBalance && (
          <BalancePanel refresh={version} />
        )}
        {mode === "own" && mayBalance && <BalancePanel own refresh={version} />}
        {(mode !== "workspace" || view === "requests") && (
          <RequestList mode={mode} refresh={version} changed={() => setVersion((v) => v + 1)} />
        )}
      </div>
      <Sheet open={creating} onOpenChange={setCreating}>
        {creating && (
          <RequestSheet
            own={mode === "own"}
            saved={() => {
              setCreating(false);
              setVersion((v) => v + 1);
              if (mode === "workspace") setView("requests");
            }}
          />
        )}
      </Sheet>
    </>
  );
}

export function RequestList({
  mode = "workspace",
  employeeId,
  refresh = 0,
  changed,
}: {
  mode?: Mode;
  employeeId?: string;
  refresh?: number;
  changed?: () => void;
}) {
  const can = useCan();
  const [rows, setRows] = useState<LeaveRequest[]>([]);
  const [busy, setBusy] = useState(true);
  const [status, setStatus] = useState("all");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [reviewing, setReviewing] = useState<LeaveRequest | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        mode === "approvals"
          ? c.GET("/leave/approvals/own")
          : mode === "own"
            ? c.GET("/leave/requests/own")
            : c.GET("/leave/requests"),
      );
      if (!active) return;
      setBusy(false);
      if (result.ok) {
        setRows(result.data);
        setProblem(null);
      } else {
        setRows([]);
        setProblem(result.problem);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [mode, refresh, version, employeeId]);
  function saved() {
    setReviewing(null);
    setVersion((v) => v + 1);
    changed?.();
  }
  async function cancel(row: LeaveRequest) {
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/leave/requests/{request_id}/cancel", { params: { path: { request_id: row.id } } }),
    );
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  const visible = rows.filter(
    (r) =>
      (!employeeId || r.employee_id === employeeId) && (status === "all" || r.status === status),
  );
  const columns: Column<LeaveRequest>[] = [
    {
      id: "employee",
      header: "Employee",
      primary: true,
      cell: (r) => r.employee_name || "Your request",
      sortValue: (r) => r.employee_name ?? "",
    },
    { id: "type", header: "Leave type", cell: (r) => r.leave_type_name || "Leave" },
    {
      id: "dates",
      header: "Dates",
      cell: (r) => `${formatUk(r.start_date)} – ${formatUk(r.end_date)}`,
    },
    { id: "days", header: "Days", cell: (r) => days(r.working_days) },
    {
      id: "status",
      header: "Status",
      cell: (r) => (
        <StatusChip
          tone={
            r.status === "approved" ? "success" : r.status === "pending" ? "warning" : "neutral"
          }
        >
          {r.status}
        </StatusChip>
      ),
    },
    { id: "note", header: "Decision note", cell: (r) => r.decision_note ?? "—" },
    {
      id: "actions",
      header: "Actions",
      cell: (r) =>
        r.status === "pending" ? (
          <div className="flex flex-wrap gap-2">
            {mode !== "own" &&
              !r.is_own &&
              can("leave.request.approve", "leave.request.approve_reports") && (
                <Button size="sm" variant="gray" onClick={() => setReviewing(r)}>
                  Review request
                </Button>
              )}
            {can("leave.request.create") || (mode === "own" && can("leave.request.create_own")) ? (
              <Button size="sm" variant="gray" onClick={() => void cancel(r)}>
                Cancel request
              </Button>
            ) : null}
          </div>
        ) : (
          "—"
        ),
    },
  ];
  return (
    <section
      aria-label={mode === "approvals" ? "Requests awaiting your decision" : "Leave requests"}
      className="flex flex-col gap-4"
    >
      <h2 className="text-title-3 text-label">
        {mode === "approvals" ? "Awaiting your decision" : "Request history"}
      </h2>
      {mode !== "approvals" && (
        <div className="max-w-xs">
          <Select label="Request status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All requests</option>
            {["pending", "approved", "rejected", "cancelled"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </div>
      )}
      {problem && <Alert tone="danger" title={problem.message} />}
      <DataTable
        caption="Leave requests"
        rows={visible}
        columns={columns}
        getRowId={(r) => r.id}
        loading={busy}
        empty={
          <EmptyState
            icon={CalendarDays}
            title={
              mode === "approvals" ? "No requests awaiting your decision" : "No leave requests"
            }
            description="Requests will appear here when submitted."
          />
        }
      />
      <Sheet
        open={reviewing !== null}
        onOpenChange={(open) => {
          if (!open) setReviewing(null);
        }}
      >
        {reviewing && <DecisionSheet request={reviewing} saved={saved} />}
      </Sheet>
    </section>
  );
}

function LeaveCalendar({ refresh }: { refresh: number }) {
  const can = useCan();
  const [month, setMonth] = useState(() => todayIso().slice(0, 7));
  const [department, setDepartment] = useState("");
  const [departments, setDepartments] = useState<components["schemas"]["DepartmentOut"][]>([]);
  const [calendar, setCalendar] = useState<components["schemas"]["CalendarOut"] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const mayDepartments = can("company.department.read");
  useEffect(() => {
    let active = true;
    if (mayDepartments)
      void attempt((c) => c.GET("/departments")).then((result) => {
        if (active && result.ok) setDepartments(result.data);
      });
    return () => {
      active = false;
    };
  }, [mayDepartments]);
  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/leave/calendar", {
        params: { query: { month, department_id: department || undefined } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) {
        setCalendar(result.data);
        setProblem(null);
      } else {
        setCalendar(null);
        setProblem(result.problem);
      }
    });
    return () => {
      active = false;
    };
  }, [month, department, refresh]);
  const [year, number] = month.split("-").map(Number);
  const grid = monthGrid(year!, number!);
  const items = calendar?.month === month ? calendar.items : [];
  return (
    <section aria-label="Leave calendar" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <TextField
          label="Month"
          type="month"
          value={month}
          required
          onChange={(e) => {
            if (e.target.value) {
              setMonth(e.target.value);
              setSelected(null);
            }
          }}
        />
        {mayDepartments && (
          <Select
            label="Department"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          >
            <option value="">All departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        )}
        <Button
          variant="gray"
          onClick={() => {
            setMonth(todayIso().slice(0, 7));
            setSelected(todayIso());
          }}
        >
          Today
        </Button>
      </div>
      {problem && <Alert tone="danger" title={problem.message} />}
      {!calendar && !problem && <p role="status">Loading calendar…</p>}
      <div className="bg-elevated rounded-card shadow-e1 overflow-hidden">
        <div className="grid grid-cols-7 text-center text-caption text-label-secondary">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <div key={d} className="p-2">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {grid.flat().map((day) => {
            const entries = items.filter((r) => r.working_dates.includes(day));
            return (
              <button
                key={day}
                aria-label={`${formatUkLong(day)}, ${entries.length} leave requests`}
                aria-pressed={selected === day}
                onClick={() => setSelected(day)}
                className={`border-separator min-h-20 min-w-0 border-t p-1 text-left focus-visible:outline-accent focus-visible:outline-2 focus-visible:-outline-offset-2 md:min-h-28 md:p-2 ${selected === day ? "bg-accent-tint" : ""} ${day.startsWith(month) ? "text-label" : "text-label-tertiary"}`}
              >
                <span className="text-caption">{Number(day.slice(-2))}</span>
                {entries.slice(0, 2).map((r) => (
                  <span key={r.id} className="mt-1 flex min-w-0 items-center gap-1 text-caption">
                    <span
                      aria-hidden
                      className={`size-1.5 shrink-0 rounded-full ${COLOUR_CLASS[r.colour as keyof typeof COLOUR_CLASS]}`}
                    />
                    <span className="truncate">{r.employee_name}</span>
                  </span>
                ))}
                {entries.length > 2 && <span className="text-caption">+{entries.length - 2}</span>}
              </button>
            );
          })}
        </div>
      </div>
      {selected && (
        <div className="bg-elevated rounded-card shadow-e1 p-4">
          <h3 className="text-headline">{formatUk(selected)}</h3>
          {items
            .filter((r) => r.working_dates.includes(selected))
            .map((r) => (
              <p key={r.id} className="mt-2 text-body">
                {r.employee_name} · {r.leave_type_name} · {r.status}
              </p>
            ))}
          {!items.some((r) => r.working_dates.includes(selected)) && (
            <p className="text-label-secondary">No leave on this day.</p>
          )}
        </div>
      )}
      <p className="text-caption text-label-secondary">
        Pending and approved requests are shown on their working days. Select a day for leave types
        and status.
      </p>
    </section>
  );
}
