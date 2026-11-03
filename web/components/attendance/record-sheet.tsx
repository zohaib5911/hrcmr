"use client";

import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { SheetContent } from "@/components/ui/sheet";
import { TextField } from "@/components/ui/text-field";
import { attempt, type Problem } from "@/lib/auth/request";
import { STATUS, type Attendance, type Person, type Status } from "@/lib/attendance";

export function RecordSheet({
  row,
  people,
  employeeId,
  on,
  timezone,
  saved,
}: {
  row: Attendance | null;
  people: Person[];
  employeeId?: string;
  on: string;
  timezone: string;
  saved: () => void;
}) {
  const [employee, setEmployee] = useState(row?.employee_id ?? employeeId ?? "");
  const [date, setDate] = useState(row?.date ?? on);
  const [status, setStatus] = useState<Status>(row?.status ?? "present");
  const [start, setStart] = useState(row?.clock_in_local ?? "09:00");
  const [end, setEnd] = useState(row?.clock_out_local ?? "17:00");
  const [unpaid, setUnpaid] = useState(String(row?.unpaid_break_minutes ?? 0));
  const [note, setNote] = useState(row?.note ?? "");
  const [startFold, setStartFold] = useState<0 | 1 | undefined>(
    row?.clock_in_fold === 1 ? 1 : row?.clock_in_fold === 0 ? 0 : undefined,
  );
  const [endFold, setEndFold] = useState<0 | 1 | undefined>(
    row?.clock_out_fold === 1 ? 1 : row?.clock_out_fold === 0 ? 0 : undefined,
  );
  const [needsFold, setNeedsFold] = useState({ start: false, end: false });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const worked = ["present", "late", "half_day"].includes(status);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.PUT("/attendance-records", {
        body: {
          employee_id: employee,
          date,
          status,
          clock_in: worked ? start : null,
          clock_out: worked ? end : null,
          unpaid_break_minutes: worked ? Number(unpaid) : 0,
          note,
          clock_in_fold: worked ? startFold : undefined,
          clock_out_fold: worked ? endFold : undefined,
        },
      }),
    );
    setBusy(false);
    if (result.ok) saved();
    else {
      setProblem(result.problem);
      if (result.problem.code === "AMBIGUOUS_LOCAL_TIME")
        setNeedsFold((old) => ({
          ...old,
          [result.problem.field === "clock_out" ? "end" : "start"]: true,
        }));
    }
  }
  return (
    <SheetContent
      title={row ? "Edit attendance" : "Record attendance"}
      description={`Times use ${timezone}. A clock-out at or before clock-in ends the following day.`}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {problem && <Alert tone="danger" title={problem.message} />}
        <Select
          label="Employee"
          required
          disabled={!!row}
          value={employee}
          onChange={(e) => setEmployee(e.target.value)}
        >
          <option value="">Choose employee</option>
          {people
            .filter((p) => p.status !== "archived" || p.id === row?.employee_id)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.first_name} {p.last_name} · {p.employee_number}
              </option>
            ))}
        </Select>
        <TextField
          label="Date"
          type="date"
          required
          disabled={!!row}
          value={date}
          onChange={(e) => {
            setDate(e.target.value);
            setStartFold(undefined);
            setEndFold(undefined);
            setNeedsFold({ start: false, end: false });
          }}
        />
        <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value as Status)}>
          {Object.entries(STATUS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        {worked && (
          <>
            <TextField
              label="Clock in"
              type="time"
              required
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                setStartFold(undefined);
                setNeedsFold((old) => ({ ...old, start: false }));
              }}
            />
            {needsFold.start && (
              <Select
                label="Clock-in repeated hour"
                value={startFold === undefined ? "" : String(startFold)}
                required
                onChange={(e) => setStartFold(Number(e.target.value) as 0 | 1)}
              >
                <option value="">Choose occurrence</option>
                <option value="0">First occurrence</option>
                <option value="1">Second occurrence</option>
              </Select>
            )}
            <TextField
              label="Clock out"
              type="time"
              required
              value={end}
              onChange={(e) => {
                setEnd(e.target.value);
                setEndFold(undefined);
                setNeedsFold((old) => ({ ...old, end: false }));
              }}
            />
            {needsFold.end && (
              <Select
                label="Clock-out repeated hour"
                value={endFold === undefined ? "" : String(endFold)}
                required
                onChange={(e) => setEndFold(Number(e.target.value) as 0 | 1)}
              >
                <option value="">Choose occurrence</option>
                <option value="0">First occurrence</option>
                <option value="1">Second occurrence</option>
              </Select>
            )}
            <TextField
              label="Unpaid break (minutes)"
              type="number"
              min="0"
              max="1440"
              step="1"
              required
              value={unpaid}
              onChange={(e) => setUnpaid(e.target.value)}
            />
          </>
        )}
        <TextField
          label="Note (optional)"
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <Button type="submit" loading={busy}>
          Save attendance
        </Button>
      </form>
    </SheetContent>
  );
}
