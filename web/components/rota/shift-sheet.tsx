"use client";

import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import { Select } from "@/components/ui/select";
import { SheetContent } from "@/components/ui/sheet";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { addDays } from "@/lib/ui/dates";

export type RotaShift = components["schemas"]["ShiftOut"];
export type ShiftTemplate = components["schemas"]["ShiftTypeOut"];
export function templateTimes(template: ShiftTemplate) {
  const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
  return {
    starts_at: template.starts_at.slice(0, 5),
    ends_at: template.ends_at.slice(0, 5),
    unpaid_break_minutes:
      template.break_start && template.break_end
        ? (mins(template.break_end) - mins(template.break_start) + 1440) % 1440
        : 0,
    shift_type_id: template.id,
  };
}

export function RotaShiftSheet({
  row,
  employee,
  date: initialDate,
  week,
  version,
  templates,
  timezone,
  writable,
  saved,
}: {
  row: RotaShift | null;
  employee: ComboboxOption;
  date: string;
  week: string;
  version: number;
  templates: ShiftTemplate[];
  timezone: string;
  writable: boolean;
  saved: () => void;
}) {
  const [person, setPerson] = useState<ComboboxOption | null>(employee);
  const [date, setDate] = useState(row?.date ?? initialDate);
  const [start, setStart] = useState(row?.starts_local ?? "09:00");
  const [end, setEnd] = useState(row?.ends_local ?? "17:00");
  const [unpaid, setUnpaid] = useState(String(row?.unpaid_break_minutes ?? 0));
  const [template, setTemplate] = useState(row?.shift_type_id ?? "");
  const [note, setNote] = useState(row?.note ?? "");
  const [startFold, setStartFold] = useState<0 | 1 | undefined>(
    row?.starts_fold === 1 ? 1 : row ? 0 : undefined,
  );
  const [endFold, setEndFold] = useState<0 | 1 | undefined>(
    row?.ends_fold === 1 ? 1 : row ? 0 : undefined,
  );
  const [needsFold, setNeedsFold] = useState({ start: false, end: false });
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!person) return;
    setBusy(true);
    setProblem(null);
    const body = {
      employee_id: person.value,
      date,
      starts_at: start,
      ends_at: end,
      unpaid_break_minutes: Number(unpaid),
      shift_type_id: template || null,
      note: note.trim() || null,
      starts_fold: startFold,
      ends_fold: endFold,
      version,
    };
    const result = await (row
      ? attempt((c) =>
          c.PUT("/rota/scheduled-shifts/{shift_id}", {
            params: { path: { shift_id: row.id } },
            body,
          }),
        )
      : attempt((c) => c.POST("/rota/scheduled-shifts", { body })));
    setBusy(false);
    if (result.ok) saved();
    else {
      setProblem(result.problem);
      if (result.problem.code === "AMBIGUOUS_LOCAL_TIME")
        setNeedsFold((old) => ({
          ...old,
          [result.problem.field === "ends_at" ? "end" : "start"]: true,
        }));
    }
  }
  async function remove() {
    if (!row) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.DELETE("/rota/scheduled-shifts/{shift_id}", {
        params: { path: { shift_id: row.id }, query: { version } },
      }),
    );
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
  const duration = start && end ? (mins(end) - mins(start) + 1440) % 1440 || 1440 : 0;
  const hours = ((duration - Number(unpaid)) / 60).toFixed(2);
  return (
    <SheetContent
      title={writable ? (row ? "Edit shift" : "Add shift") : "View shift"}
      description={`Times use ${timezone}. An earlier finish ends the following day.`}
    >
      <form className="flex flex-col gap-4" onSubmit={(event) => void submit(event)}>
        {problem && <Alert tone="danger" title={problem.message} />}
        <fieldset disabled={busy || !writable} className="flex min-w-0 flex-col gap-4">
          <Combobox
            label="Employee"
            required
            value={person}
            onChange={setPerson}
            minChars={0}
            loadOptions={async (q, signal) => {
              const result = await attempt((c) =>
                c.GET("/employees", { params: { query: { q } }, signal }),
              );
              if (!result.ok) throw new Error(result.problem.message);
              return result.data.employees.map((p) => ({
                value: p.id,
                label: `${p.first_name} ${p.last_name}`,
                description: p.employee_number,
              }));
            }}
          />
          <TextField
            label="Shift date"
            type="date"
            required
            min={week}
            max={addDays(week, 6)}
            value={date}
            onChange={(e) => {
              setDate(e.target.value);
              setStartFold(undefined);
              setEndFold(undefined);
            }}
          />
          <Select
            label="Shift type (optional)"
            value={template}
            onChange={(e) => {
              setTemplate(e.target.value);
              const selected = templates.find((t) => t.id === e.target.value);
              if (selected) {
                const times = templateTimes(selected);
                setStart(times.starts_at);
                setEnd(times.ends_at);
                setUnpaid(String(times.unpaid_break_minutes));
                setStartFold(undefined);
                setEndFold(undefined);
              }
            }}
          >
            <option value="">Custom shift</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Starts"
              type="time"
              required
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                setStartFold(undefined);
              }}
            />
            <TextField
              label="Finishes"
              type="time"
              required
              value={end}
              onChange={(e) => {
                setEnd(e.target.value);
                setEndFold(undefined);
              }}
            />
          </div>
          {needsFold.start && (
            <Select
              label="Starts occurrence"
              value={startFold ?? ""}
              onChange={(e) =>
                setStartFold(e.target.value === "" ? undefined : (Number(e.target.value) as 0 | 1))
              }
            >
              <option value="">Choose the occurrence</option>
              <option value={0}>First occurrence</option>
              <option value={1}>Second occurrence</option>
            </Select>
          )}
          {needsFold.end && (
            <Select
              label="Finishes occurrence"
              value={endFold ?? ""}
              onChange={(e) =>
                setEndFold(e.target.value === "" ? undefined : (Number(e.target.value) as 0 | 1))
              }
            >
              <option value="">Choose the occurrence</option>
              <option value={0}>First occurrence</option>
              <option value={1}>Second occurrence</option>
            </Select>
          )}
          <TextField
            label="Unpaid break (minutes)"
            type="number"
            min={0}
            max={1440}
            required
            value={unpaid}
            onChange={(e) => setUnpaid(e.target.value)}
          />
          <p role="status">{hours} hours paid before any clock-change adjustment.</p>
          <TextArea
            label="Shift note (optional)"
            maxLength={2000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </fieldset>
        {writable && (
          <div className="flex flex-wrap gap-3">
            <Button type="submit" loading={busy} disabled={!person}>
              Save shift
            </Button>
            {row && (
              <InlineConfirm
                label="Remove shift"
                prompt="Remove this shift from the draft rota?"
                confirmLabel="Remove shift"
                destructive
                disabled={busy}
                onConfirm={remove}
              />
            )}
          </div>
        )}
      </form>
    </SheetContent>
  );
}
