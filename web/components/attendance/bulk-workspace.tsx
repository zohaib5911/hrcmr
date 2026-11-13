"use client";

import Link from "next/link";
import { Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { STATUS, type Status } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays, formatUk, startOfWeek, todayIso } from "@/lib/ui/dates";

type Grid = components["schemas"]["GridOut"];
type Entry = components["schemas"]["GridRow"];

export function AttendanceBulk() {
  const can = useCan();
  const [start, setStart] = useState(() => startOfWeek(todayIso()));
  const [offset, setOffset] = useState(0);
  const [grid, setGrid] = useState<Grid | null>(null);
  const [loadedKey, setLoadedKey] = useState("");
  const [changes, setChanges] = useState<Record<string, Entry>>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const key = `${start}:${offset}:${version}`;
  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/attendance/grid", { params: { query: { start, offset } } })).then(
      (result) => {
        if (!active) return;
        setLoadedKey(key);
        if (result.ok) {
          setGrid(result.data);
          setProblem(null);
        } else {
          setGrid(null);
          setProblem(result.problem);
        }
      },
    );
    return () => {
      active = false;
    };
  }, [start, offset, version, key]);
  async function save() {
    setBusy(true);
    setProblem(null);
    setSaved(null);
    const result = await attempt((c) =>
      c.PUT("/attendance/grid", { body: { rows: Object.values(changes) } }),
    );
    setBusy(false);
    if (result.ok) {
      setChanges({});
      setSaved(result.data.count);
      setVersion((v) => v + 1);
    } else setProblem(result.problem);
  }
  const dirty = Object.keys(changes).length;
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const records = new Map(grid?.records.map((r) => [`${r.employee_id}:${r.date}`, r]));
  const locked = busy || dirty > 0;
  return (
    <>
      <PageHeader
        title="Bulk attendance"
        description="Choose statuses across a week, then save your changes together."
        actions={
          <Button asChild variant="gray">
            <Link href="/attendance">Attendance</Link>
          </Button>
        }
      />
      {!can("attendance.record.write") ? (
        <Alert title="Bulk entry needs company-wide write access." />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-end gap-3">
            <Button
              variant="gray"
              disabled={locked}
              onClick={() => {
                setStart(addDays(start, -7));
                setOffset(0);
              }}
            >
              Previous week
            </Button>
            <TextField
              label="Week containing"
              type="date"
              value={start}
              disabled={locked}
              onChange={(e) => {
                if (e.target.value) {
                  setStart(startOfWeek(e.target.value));
                  setOffset(0);
                }
              }}
            />
            <Button
              variant="gray"
              disabled={locked}
              onClick={() => {
                setStart(addDays(start, 7));
                setOffset(0);
              }}
            >
              Next week
            </Button>
          </div>
          <p className="text-callout text-label-secondary">
            Existing worked times, breaks and notes are retained when you change a status. New
            worked entries have no hours until clock times are recorded. Absence statuses clear
            clock times. Approved leave is protected.
          </p>
          {problem && <Alert tone="danger" title={problem.message} />}
          {saved !== null && <Alert tone="success" title={`${saved} attendance records saved`} />}
          {loadedKey !== key ? (
            <p role="status">Loading attendance…</p>
          ) : grid && grid.people.length === 0 ? (
            // A table with headers and no rows reads as broken to a screen reader.
            <EmptyState
              icon={Clock}
              title="No employees this week"
              description="Add employees, or choose a week when they were employed."
            />
          ) : (
            grid && (
              <>
                <p className="text-caption text-label-secondary">
                  {formatUk(grid.start)} to {formatUk(grid.end)} · {grid.timezone}
                </p>
                <div
                  className="overflow-x-auto rounded-card border border-separator"
                  role="region"
                  aria-label="Weekly attendance grid"
                  tabIndex={0}
                >
                  <table className="w-full text-callout text-label">
                    <caption className="sr-only">Weekly attendance status entry</caption>
                    <thead className="bg-elevated">
                      <tr>
                        <th scope="col" className="p-3 text-left">
                          Employee
                        </th>
                        {days.map((day) => (
                          <th key={day} scope="col" className="p-3 text-left whitespace-nowrap">
                            {formatUk(day)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {grid.people.map((person) => (
                        <tr key={person.id} className="border-t border-separator">
                          <th scope="row" className="p-3 text-left">
                            <span className="block whitespace-nowrap">{person.name}</span>
                            <span className="text-caption text-label-secondary">
                              {person.employee_number}
                            </span>
                          </th>
                          {days.map((day) => {
                            const id = `${person.id}:${day}`;
                            const record = records.get(id);
                            const protectedLeave =
                              record?.source === "leave_sync" || !!record?.leave_request_id;
                            const outside =
                              day < person.hire_date ||
                              (!!person.leave_date && day > person.leave_date);
                            const value = changes[id]?.status ?? record?.status ?? "";
                            return (
                              <td key={day} className="min-w-40 p-2">
                                <select
                                  aria-label={`${person.name}, ${formatUk(day)}`}
                                  className="bg-fill-secondary text-label rounded-control w-full min-h-11 px-3"
                                  value={value}
                                  disabled={busy || protectedLeave || outside}
                                  onChange={(e) => {
                                    const status = e.target.value as Status | "";
                                    setSaved(null);
                                    setChanges((old) => {
                                      const next = { ...old };
                                      if (!status || status === record?.status) delete next[id];
                                      else next[id] = { employee_id: person.id, date: day, status };
                                      return next;
                                    });
                                  }}
                                >
                                  <option value="" disabled={!!record}>
                                    Not recorded
                                  </option>
                                  {Object.entries(STATUS).map(([value, label]) => (
                                    <option key={value} value={value}>
                                      {label}
                                    </option>
                                  ))}
                                </select>
                                {protectedLeave ? (
                                  <span className="text-caption text-label-secondary">
                                    Approved leave
                                  </span>
                                ) : outside ? (
                                  <span className="text-caption text-label-secondary">
                                    Outside employment
                                  </span>
                                ) : record?.hours != null ? (
                                  <span className="text-caption text-label-secondary">
                                    {record.hours} hours
                                  </span>
                                ) : null}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!grid.people.length && <p className="p-4">No employees for this week.</p>}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <Button loading={busy} disabled={!dirty} onClick={() => void save()}>
                    Save {dirty || ""} changes
                  </Button>
                  <Button variant="gray" disabled={busy || !dirty} onClick={() => setChanges({})}>
                    Discard changes
                  </Button>
                  <span className="text-caption text-label-secondary" aria-live="polite">
                    {dirty} unsaved changes
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="gray"
                    disabled={locked || offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - 20))}
                  >
                    Previous employees
                  </Button>
                  <Button
                    variant="gray"
                    disabled={locked || grid.next_offset === null}
                    onClick={() => setOffset(grid.next_offset ?? 0)}
                  >
                    Next employees
                  </Button>
                </div>
              </>
            )
          )}
        </div>
      )}
    </>
  );
}
