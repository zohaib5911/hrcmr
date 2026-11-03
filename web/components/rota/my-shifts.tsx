"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { ClockLink } from "@/components/attendance/clock";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays, formatUk, parseIso, startOfWeek, todayIso } from "@/lib/ui/dates";

type Own = components["schemas"]["OwnShifts"];
type Shift = components["schemas"]["ShiftOut"];

export function MyShiftsLink() {
  const can = useCan();
  return can("rota.scheduled_shift.read_own") ? (
    <Button asChild variant="gray">
      <Link href="/my-shifts">My shifts</Link>
    </Button>
  ) : null;
}

export function MyShifts({ initialWeek }: { initialWeek?: string }) {
  const [start, setStart] = useState(() =>
    initialWeek && parseIso(initialWeek) ? startOfWeek(initialWeek) : startOfWeek(todayIso()),
  );
  const [data, setData] = useState<Own | null>(null);
  const [loaded, setLoaded] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [version, setVersion] = useState(0);
  const key = `${start}:${version}`;
  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/rota/own", { params: { query: { start, end: addDays(start, 6) } } }),
    ).then((result) => {
      if (!active) return;
      setLoaded(key);
      if (result.ok) {
        setData(result.data);
        setProblem(null);
      } else {
        setData(null);
        setProblem(result.problem);
      }
    });
    return () => {
      active = false;
    };
  }, [start, version, key]);
  const columns: Column<Shift>[] = [
    { id: "date", header: "Date", primary: true, cell: (s) => formatUk(s.date) },
    { id: "type", header: "Shift", cell: (s) => s.shift_name ?? "Custom shift" },
    { id: "start", header: "Starts", cell: (s) => s.starts_local },
    { id: "end", header: "Finishes", cell: (s) => s.ends_local },
    { id: "break", header: "Break", cell: (s) => `${s.unpaid_break_minutes} minutes` },
    { id: "hours", header: "Paid hours", cell: (s) => s.hours },
    {
      id: "note",
      header: "Note",
      cell: (s) => <span className="whitespace-pre-wrap break-words">{s.note || "—"}</span>,
    },
  ];
  return (
    <>
      <PageHeader
        title="My shifts"
        description="Your latest published schedule."
        actions={<ClockLink />}
      />
      <div className="flex min-w-0 flex-col gap-5">
        <div className="flex flex-wrap items-end gap-3">
          <Button variant="gray" onClick={() => setStart(addDays(start, -7))}>
            Previous week
          </Button>
          <TextField
            label="My shifts week containing"
            type="date"
            value={start}
            onChange={(e) => {
              if (e.target.value) setStart(startOfWeek(e.target.value));
            }}
          />
          <Button variant="gray" onClick={() => setStart(addDays(start, 7))}>
            Next week
          </Button>
          <Button variant="gray" onClick={() => setVersion((v) => v + 1)}>
            Reload shifts
          </Button>
        </div>
        {problem && <Alert tone="danger" title={problem.message} />}
        <p className="text-callout text-label-secondary">
          Draft changes appear after publication. An earlier finish ends the following day.{" "}
          {data?.timezone}
        </p>
        <DataTable
          caption="My published shifts"
          rows={loaded === key ? (data?.shifts ?? []) : []}
          columns={columns}
          getRowId={(s) => s.id}
          loading={loaded !== key}
        />
        {loaded === key && data && !data.shifts.length && <p>No published shifts this week.</p>}
      </div>
    </>
  );
}
