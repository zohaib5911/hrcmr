"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";
import type { components } from "@/lib/api/client";
import { todayIso } from "@/lib/ui/dates";

export type Balance = components["schemas"]["BalanceOut"];
export const days = (value: string | number | null) =>
  value === null
    ? "Unavailable"
    : Number(value).toLocaleString("en-GB", { maximumFractionDigits: 2 });

export function BalancePanel({
  employeeId,
  own = false,
  refresh = 0,
}: {
  employeeId?: string;
  own?: boolean;
  refresh?: number;
}) {
  const can = useCan();
  const [on, setOn] = useState(todayIso);
  const [rows, setRows] = useState<Balance[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [busy, setBusy] = useState(true);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [editing, setEditing] = useState<Balance | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        employeeId
          ? c.GET("/employees/{employee_id}/leave-balances", {
              params: { path: { employee_id: employeeId }, query: { on } },
            })
          : own
            ? c.GET("/leave-balances/own", { params: { query: { on } } })
            : c.GET("/leave-balances", { params: { query: { on } } }),
      );
      if (!active) return;
      setBusy(false);
      if (result.ok) {
        setRows(result.data.items);
        setNextOffset(result.data.next_offset);
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
  }, [employeeId, own, on, refresh, version]);
  async function more() {
    if (nextOffset === null) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.GET("/leave-balances", { params: { query: { on, offset: nextOffset } } }),
    );
    setBusy(false);
    if (result.ok) {
      setRows([...rows, ...result.data.items]);
      setNextOffset(result.data.next_offset);
    } else setProblem(result.problem);
  }
  const columns: Column<Balance>[] = [
    ...(!own && !employeeId
      ? [
          {
            id: "employee",
            header: "Employee",
            primary: true,
            cell: (r: Balance) => r.employee_name,
            sortValue: (r: Balance) => r.employee_name,
          },
        ]
      : []),
    {
      id: "type",
      header: "Leave type",
      primary: own || !!employeeId,
      cell: (r) => r.leave_type_name,
      sortValue: (r) => r.leave_type_name,
    },
    {
      id: "available",
      header: "Available days",
      cell: (r) => days(r.available),
      sortValue: (r) => (r.available === null ? null : Number(r.available)),
    },
    { id: "taken", header: "Taken", cell: (r) => days(r.taken) },
    { id: "pending", header: "Pending", cell: (r) => days(r.pending) },
    ...(can("leave.accrual.write")
      ? [
          {
            id: "actions",
            header: "Actions",
            cell: (r: Balance) => (
              <Button size="sm" variant="gray" onClick={() => setEditing(r)}>
                Adjust {r.leave_type_name}
              </Button>
            ),
          },
        ]
      : []),
  ];
  return (
    <section aria-label="Leave balances" className="flex flex-col gap-4">
      <div className="max-w-xs">
        <TextField
          type="date"
          label="Allowance as of"
          value={on}
          onChange={(e) => {
            setBusy(true);
            setOn(e.target.value);
          }}
        />
      </div>
      <p className="text-callout text-label-secondary">
        Available days include your calculated allowance and bank holidays or closures. Pending
        requests are shown separately. Quantities use standard company days.
      </p>
      {problem && <Alert tone="danger" title={problem.message} />}
      {rows
        .filter((r) => r.calculation_issue)
        .map((r) => (
          <Alert
            key={r.employee_id + r.leave_type_id}
            tone="warning"
            title={`${r.employee_name} · ${r.leave_type_name}`}
          >
            <p>{r.calculation_issue}</p>
          </Alert>
        ))}
      <DataTable
        caption="Leave balances"
        columns={columns}
        rows={rows}
        getRowId={(r) => r.employee_id + r.leave_type_id}
        loading={busy}
        empty={
          <p className="p-6 text-label-secondary">
            No balances available. Your account may need a linked employee record.
          </p>
        }
      />
      {nextOffset !== null && (
        <Button variant="gray" loading={busy} onClick={() => void more()}>
          Load more employees
        </Button>
      )}
      <Sheet
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
      >
        {editing && (
          <BalanceSheet
            key={editing.employee_id + editing.leave_type_id}
            balance={editing}
            on={on}
            saved={() => {
              setEditing(null);
              setVersion((v) => v + 1);
            }}
          />
        )}
      </Sheet>
    </section>
  );
}

function BalanceSheet({ balance, on, saved }: { balance: Balance; on: string; saved: () => void }) {
  const [operation, setOperation] = useState<"grant" | "deduct" | "set">("grant");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [key] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    const path = { employee_id: balance.employee_id };
    const body = {
      leave_type_id: balance.leave_type_id,
      on,
      days: amount,
      reason,
      idempotency_key: key,
    };
    const result = await attempt((c) =>
      operation === "grant"
        ? c.POST("/employees/{employee_id}/leave-balances/grant", { params: { path }, body })
        : operation === "deduct"
          ? c.POST("/employees/{employee_id}/leave-balances/deduct", { params: { path }, body })
          : c.POST("/employees/{employee_id}/leave-balances/set", { params: { path }, body }),
    );
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  return (
    <SheetContent
      title={`Adjust ${balance.leave_type_name}`}
      description={`${balance.employee_name} · Available: ${days(balance.available)} days`}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {problem && <Alert tone="danger" title={problem.message} />}
        <Select
          label="Action"
          value={operation}
          onChange={(e) => setOperation(e.target.value as typeof operation)}
        >
          <option value="grant">Grant</option>
          <option value="deduct">Deduct</option>
          <option value="set">Set balance</option>
        </Select>
        <TextField
          label={operation === "set" ? "New balance (days)" : "Days"}
          type="number"
          step="0.01"
          required
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <TextField
          label="Reason"
          required
          maxLength={1000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <p className="text-caption text-label-secondary">
          This change is recorded in the leave history with your name and reason.
        </p>
        <Button type="submit" loading={busy}>
          Save balance
        </Button>
      </form>
    </SheetContent>
  );
}
