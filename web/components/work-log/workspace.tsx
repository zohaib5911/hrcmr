"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { KpiCard } from "@/components/ui/kpi-card";
import { Select } from "@/components/ui/select";
import { Sheet } from "@/components/ui/sheet";
import { TextArea } from "@/components/ui/text-area";
import { DatePicker } from "@/components/ui/date-picker";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk, todayIso } from "@/lib/ui/dates";
import { WorkLogSheet, type Entry, type Responsibility } from "./entry-sheet";

type Page = components["schemas"]["WorkLogPage"];
type Person = components["schemas"]["EmployeeRow"];
type Opened = { row: Entry | null; mode: "new" | "edit" | "correct" | "view" };

export function WorkLogWorkspace({ own: ownProp = false }: { own?: boolean }) {
  const can = useCan();
  const own = ownProp || !can("work_log.entry.read");
  const mayWrite = can("work_log.entry.write_own");
  const mayCorrect = can("work_log.entry.correct");
  const [start, setStart] = useState(() => todayIso().slice(0, 7) + "-01");
  const [end, setEnd] = useState(todayIso);
  const [search, setSearch] = useState("");
  const [employee, setEmployee] = useState("");
  const [showRemoved, setShowRemoved] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [offset, setOffset] = useState(0);
  const [people, setPeople] = useState<Person[]>([]);
  const [responsibilities, setResponsibilities] = useState<Responsibility[]>([]);
  const [data, setData] = useState<Page | null>(null);
  const [loaded, setLoaded] = useState("");
  const [version, setVersion] = useState(0);
  const [opened, setOpened] = useState<Opened | null>(null);
  const [remove, setRemove] = useState<Entry | null>(null);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const key = JSON.stringify([
    own,
    start,
    end,
    employee,
    search,
    showRemoved,
    showArchived,
    offset,
    version,
  ]);
  useEffect(() => {
    let active = true;
    const base = { start, end, offset };
    void (
      own
        ? attempt((c) => c.GET("/work-log/own", { params: { query: base } }))
        : attempt((c) =>
            c.GET("/work-log", {
              params: {
                query: {
                  ...base,
                  employee_id: employee || undefined,
                  search,
                  show_removed: showRemoved,
                  show_archived: showArchived,
                },
              },
            }),
          )
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
  }, [own, start, end, employee, search, showRemoved, showArchived, offset, version, key]);
  useEffect(() => {
    let active = true;
    if (!own)
      void attempt((c) =>
        c.GET("/employees", { params: { query: { archived: showArchived } } }),
      ).then((result) => {
        if (active && result.ok) setPeople(result.data.employees);
      });
    if (own)
      void attempt((c) => c.GET("/work-log/own/responsibilities")).then((result) => {
        if (active && result.ok) setResponsibilities(result.data);
      });
    return () => {
      active = false;
    };
  }, [own, showArchived, version]);
  const current = loaded === key ? data : null;
  function changed() {
    setOpened(null);
    setRemove(null);
    setProblem(null);
    setVersion((v) => v + 1);
  }
  async function removeEntry() {
    if (!remove) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/work-log/{entry_id}/remove", {
        params: { path: { entry_id: remove.id } },
        body: { reason, revision: remove.revision },
      }),
    );
    setBusy(false);
    if (result.ok) changed();
    else setProblem(result.problem);
  }
  const columns: Column<Entry>[] = [
    { id: "employee", header: "Employee", primary: !own, cell: (r) => r.employee_name },
    { id: "date", header: "Date", primary: own, cell: (r) => formatUk(r.date) },
    {
      id: "time",
      header: "Time",
      cell: (r) => `${r.from_time.slice(0, 5)}–${r.to_time.slice(0, 5)}`,
    },
    { id: "hours", header: "Hours", cell: (r) => r.hours },
    {
      id: "responsibility",
      header: "Responsibility",
      cell: (r) => (
        <span className="block max-w-xs whitespace-pre-wrap break-words">
          {r.responsibility_text}
        </span>
      ),
    },
    {
      id: "description",
      header: "What I did",
      cell: (r) => (
        <span className="block max-w-xs whitespace-pre-wrap break-words">{r.description}</span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (r) => (r.removed_at ? "Removed" : r.corrected_from ? "Corrected" : "Logged"),
    },
    {
      id: "open",
      header: "Open",
      cell: (r) => (
        <Button
          variant="gray"
          size="sm"
          onClick={() =>
            setOpened({
              row: r,
              mode:
                own && r.can_edit
                  ? "edit"
                  : !own && mayCorrect && !r.removed_at
                    ? "correct"
                    : "view",
            })
          }
        >
          {own && r.can_edit
            ? "Edit entry"
            : !own && mayCorrect && !r.removed_at
              ? "Correct entry"
              : "View entry"}
        </Button>
      ),
    },
    {
      id: "remove",
      header: "Remove",
      cell: (r) =>
        !r.removed_at ? (
          <Button
            variant="plain"
            size="sm"
            onClick={() => {
              setRemove(r);
              setReason("");
              setProblem(null);
            }}
          >
            Remove entry
          </Button>
        ) : null,
    },
  ];
  return (
    <>
      <PageHeader
        title={own ? "My work log" : "Work log"}
        description={
          own
            ? "Your daily responsibilities and work completed."
            : "Review work in a date range and make reasoned corrections."
        }
        actions={
          own
            ? mayWrite && (
                <Button disabled={!current} onClick={() => setOpened({ row: null, mode: "new" })}>
                  Add entry
                </Button>
              )
            : can("work_log.entry.read_own", "work_log.entry.write_own") && (
                <Button asChild variant="gray">
                  <Link href="/my-work-log">My work log</Link>
                </Button>
              )
        }
      />
      <div className="flex min-w-0 flex-col gap-5">
        {problem && !remove && <Alert tone="danger" title={problem.message} />}
        <div className="flex flex-wrap items-end gap-3">
          <DatePicker
            label="From date"
            value={start || null}
            onChange={(picked) => {
              if (picked ?? "") {
                setStart(picked ?? "");
                setOffset(0);
              }
            }}
          />
          <DatePicker
            label="To date"
            value={end || null}
            onChange={(picked) => {
              if (picked ?? "") {
                setEnd(picked ?? "");
                setOffset(0);
              }
            }}
          />
          {!own && (
            <>
              <TextField
                label="Search work log"
                maxLength={100}
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
              />
              <Select
                label="Employee"
                value={employee}
                onChange={(e) => {
                  setEmployee(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All employees</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name}
                  </option>
                ))}
              </Select>
            </>
          )}
          <Button variant="gray" onClick={() => setVersion((v) => v + 1)}>
            Reload work log
          </Button>
        </div>
        {!own && (
          <div className="flex flex-wrap gap-6">
            <Checkbox
              label="Show removed"
              checked={showRemoved}
              onCheckedChange={(v) => {
                setShowRemoved(v === true);
                setOffset(0);
              }}
            />
            <Checkbox
              label="Show archived"
              checked={showArchived}
              onCheckedChange={(v) => {
                setShowArchived(v === true);
                setOffset(0);
              }}
            />
          </div>
        )}
        {current && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <KpiCard label="Entries in range" value={current.total} />
            <KpiCard label="Hours logged" value={Number(current.hours)} />
            {!own && <KpiCard label="Employees" value={current.employees} />}
          </div>
        )}
        {own && (
          <p className="text-callout text-label-secondary">
            You can edit an entry on its work date. Ask an administrator to correct an older entry.{" "}
            {current?.timezone}
          </p>
        )}
        <DataTable
          caption={own ? "My work log entries" : "Work log entries"}
          columns={columns.filter(
            (c) => (c.id !== "employee" || !own) && (c.id !== "remove" || (!own && mayCorrect)),
          )}
          rows={current?.items ?? []}
          loading={!current && !problem}
          getRowId={(r) => r.id}
          onRowOpen={(row) => setOpened({ row, mode: "view" })}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            variant="gray"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            Previous entries
          </Button>
          <Button
            variant="gray"
            disabled={!current || current.next_offset == null}
            onClick={() => setOffset(current?.next_offset ?? 0)}
          >
            Next entries
          </Button>
        </div>
      </div>
      <Sheet
        open={opened !== null}
        onOpenChange={(open) => {
          if (!open) setOpened(null);
        }}
      >
        {opened && data && (
          <WorkLogSheet
            key={`${opened.row?.id ?? "new"}:${opened.mode}`}
            row={opened.row}
            mode={opened.mode}
            responsibilities={own ? responsibilities : []}
            today={data.today}
            timezone={data.timezone}
            saved={changed}
          />
        )}
      </Sheet>
      <Dialog
        open={remove !== null}
        onOpenChange={(open) => {
          if (!open && !busy) {
            setRemove(null);
            setProblem(null);
          }
        }}
      >
        <DialogContent
          title="Remove work log entry"
          description="The entry will be retained and hidden from active results. Your reason is audited."
          footer={
            <>
              <Button
                variant="gray"
                disabled={busy}
                onClick={() => {
                  setRemove(null);
                  setProblem(null);
                }}
              >
                Cancel
              </Button>
              <Button type="submit" form="remove-work-log" variant="destructive" loading={busy}>
                Remove entry
              </Button>
            </>
          }
        >
          <form
            id="remove-work-log"
            onSubmit={(e) => {
              e.preventDefault();
              void removeEntry();
            }}
            className="flex flex-col gap-4"
          >
            {problem && <Alert tone="danger" title={problem.message} />}
            <TextArea
              label="Reason for removal"
              required
              maxLength={1000}
              disabled={busy}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
