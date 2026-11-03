"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { todayIso } from "@/lib/ui/dates";
import { days } from "./balances";

type Preview = components["schemas"]["YearEndPreview"];
type Row = components["schemas"]["CarryRow"];
type Override = components["schemas"]["CarryOverride"];
const rowId = (r: { employee_id: string; leave_type_id: string }) =>
  r.employee_id + ":" + r.leave_type_id;

export function YearEndPage({ startMonthDay }: { startMonthDay: string }) {
  const [from, setFrom] = useState(() => {
    const today = todayIso();
    const year = Number(today.slice(0, 4)) - (today.slice(5) >= startMonthDay ? 1 : 2);
    return `${year}-${startMonthDay}`;
  });
  const [review, setReview] = useState<Preview | null>(null);
  const [overrides, setOverrides] = useState<Override[]>([]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  async function preview(next = overrides) {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/leave/year-end/preview", { body: { from_year: from, overrides: next } }),
    );
    setBusy(false);
    if (result.ok) {
      setReview(result.data);
      setOverrides(next);
      setEditing(null);
    } else setProblem(result.problem);
  }
  async function commit() {
    if (!review) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/leave/year-end/commit", {
        body: { from_year: from, overrides, preview_token: review.preview_token },
      }),
    );
    setBusy(false);
    if (result.ok) setReview(result.data);
    else setProblem(result.problem);
  }
  const columns: Column<Row>[] = [
    {
      id: "employee",
      header: "Employee",
      primary: true,
      cell: (r) => r.employee_name,
      sortValue: (r) => r.employee_name,
    },
    { id: "type", header: "Leave type", cell: (r) => r.leave_type_name },
    { id: "remaining", header: "Remaining days", cell: (r) => days(r.remaining) },
    { id: "limit", header: "Standard limit", cell: (r) => days(r.limit) },
    { id: "carry", header: "Carry forward", cell: (r) => days(r.carry) },
    { id: "expire", header: "Expires", cell: (r) => days(r.expire) },
    {
      id: "reason",
      header: "Override reason",
      cell: (r) => r.override_reason || "Standard policy",
    },
    ...(!review?.committed_run_id
      ? [
          {
            id: "action",
            header: "Review",
            cell: (r: Row) => (
              <Button
                variant="gray"
                size="sm"
                disabled={busy}
                onClick={() => {
                  setProblem(null);
                  setEditing(r);
                }}
              >
                Override {r.leave_type_name}
              </Button>
            ),
          },
        ]
      : []),
  ];
  return (
    <>
      <PageHeader
        title="Leave year end"
        description="Review carry-over and exceptions before closing a leave year."
        actions={
          <Button asChild variant="gray">
            <Link href="/leave/settings">Leave settings</Link>
          </Button>
        }
      />
      <div className="flex flex-col gap-5">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void preview();
          }}
        >
          <TextField
            type="date"
            label="Leave year starts"
            disabled={busy}
            required
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setReview(null);
              setOverrides([]);
            }}
            hint={`Your leave year starts ${startMonthDay}.`}
          />
          <Button type="submit" loading={busy}>
            Preview year
          </Button>
        </form>
        <p className="text-callout text-label-secondary">
          Carry-over uses the positive balance up to each type’s limit. Record a reason for
          exceptions such as reviewed sickness or family leave. Resolve pending requests and
          negative fixed allowances before closing. Closing moves carry-over into the next year,
          expires the remainder and locks the source year.
        </p>
        {problem && <Alert tone="danger" title={problem.message} />}
        {review && (
          <>
            <h2 className="text-title-3 text-label">
              {review.from_year} to {review.to_year}
            </h2>
            {review.committed_run_id && (
              <Alert tone="success" title="Leave year closed">
                <p>The carry-over and closing movements are recorded in the ledger.</p>
              </Alert>
            )}
            {!review.committed_run_id &&
              review.blockers.map((b, i) => <Alert key={i} tone="warning" title={b} />)}
            <p role="status" className="text-headline text-label">
              {days(review.rows.reduce((sum, r) => sum + Number(r.carry), 0))} days to carry forward
              · {days(review.rows.reduce((sum, r) => sum + Number(r.expire), 0))} days expire
            </p>
            <DataTable
              caption="Year-end carry-over"
              columns={columns}
              rows={review.rows.filter(
                (r) => r.remaining === null || Number(r.remaining) !== 0 || Number(r.carry) !== 0,
              )}
              getRowId={rowId}
              empty={
                <p className="p-6 text-label-secondary">
                  There are no remaining balances to carry forward.
                </p>
              }
            />
            {!review.committed_run_id && (
              <div>
                <InlineConfirm
                  label="Commit year end"
                  prompt="Close this leave year and post the reviewed carry-over?"
                  confirmLabel="Close leave year"
                  disabled={busy || review.blockers.length > 0}
                  onConfirm={commit}
                />
              </div>
            )}
          </>
        )}
      </div>
      <Sheet
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setEditing(null);
        }}
      >
        {editing && (
          <OverrideSheet
            key={rowId(editing)}
            row={editing}
            problem={problem}
            busy={busy}
            save={(amount, reason) =>
              preview([
                ...overrides.filter((o) => rowId(o) !== rowId(editing)),
                {
                  employee_id: editing.employee_id,
                  leave_type_id: editing.leave_type_id,
                  days: amount,
                  reason,
                },
              ])
            }
            reset={() => preview(overrides.filter((o) => rowId(o) !== rowId(editing)))}
          />
        )}
      </Sheet>
    </>
  );
}

function OverrideSheet({
  row,
  problem,
  busy,
  save,
  reset,
}: {
  row: Row;
  problem: Problem | null;
  busy: boolean;
  save: (amount: string, reason: string) => Promise<void>;
  reset: () => Promise<void>;
}) {
  const [amount, setAmount] = useState(String(row.carry));
  const [reason, setReason] = useState(row.override_reason || "");
  function submit(event: FormEvent) {
    event.preventDefault();
    void save(amount, reason);
  }
  return (
    <SheetContent
      title={`Override ${row.leave_type_name}`}
      description={`${row.employee_name} · ${days(row.remaining)} days remaining`}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {problem && <Alert tone="danger" title={problem.message} />}
        <TextField
          label="Carry-over days"
          type="number"
          step="0.01"
          min="0"
          max={row.remaining ?? undefined}
          required
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <TextField
          label="Override reason"
          required
          maxLength={1000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <Button loading={busy} type="submit">
          Apply override
        </Button>
        <Button variant="gray" disabled={busy} onClick={() => void reset()}>
          Use standard policy
        </Button>
      </form>
    </SheetContent>
  );
}
