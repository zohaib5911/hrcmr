"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { SheetContent } from "@/components/ui/sheet";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { todayIso } from "@/lib/ui/dates";
import { days } from "./balances";

type Kind = components["schemas"]["LeaveTypeOut"];
type Person = components["schemas"]["EmployeeRow"];
type Preview = components["schemas"]["LeavePreview"];
export type LeaveRequest = components["schemas"]["LeaveRequestOut"];

export function RequestSheet({ own, saved }: { own: boolean; saved: () => void }) {
  const [types, setTypes] = useState<Kind[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [employee, setEmployee] = useState("");
  const [kind, setKind] = useState("");
  const [start, setStart] = useState(todayIso);
  const [end, setEnd] = useState(todayIso);
  const [halfStart, setHalfStart] = useState(false);
  const [halfEnd, setHalfEnd] = useState(false);
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const body = useMemo(
    () => ({
      leave_type_id: kind,
      start_date: start,
      end_date: end,
      half_day_start: halfStart,
      half_day_end: halfEnd,
      note,
    }),
    [kind, start, end, halfStart, halfEnd, note],
  );
  const currentKey = JSON.stringify([body, employee]);
  useEffect(() => {
    let active = true;
    async function load() {
      const kinds = await attempt((c) => c.GET("/leave/types"));
      if (!active) return;
      if (kinds.ok) {
        setTypes(kinds.data);
        setKind(kinds.data[0]?.id ?? "");
      } else setProblem(kinds.problem);
      if (!own) {
        const result = await attempt((c) => c.GET("/employees"));
        if (!active) return;
        if (result.ok) setPeople(result.data.employees.filter((p) => p.status !== "archived"));
        else setProblem(result.problem);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [own]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      if (!kind || !start || !end || (!own && !employee)) return;
      const result = await attempt((c) =>
        own
          ? c.POST("/leave/requests/own/preview", { body })
          : c.POST("/leave/requests/preview", { body: { ...body, employee_id: employee } }),
      );
      if (!active) return;
      if (result.ok) {
        setPreview(result.data);
        setPreviewKey(currentKey);
        setProblem(null);
      } else {
        setPreview(null);
        setProblem(result.problem);
      }
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [body, kind, start, end, own, employee, currentKey]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      own
        ? c.POST("/leave/requests/own", { body })
        : c.POST("/leave/requests", { body: { ...body, employee_id: employee } }),
    );
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  const ready = preview && previewKey === currentKey;
  return (
    <SheetContent
      title={own ? "Request leave" : "Request leave on behalf"}
      description="Review working days and team coverage before submitting."
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {problem && <Alert tone="danger" title={problem.message} />}
        {!own && (
          <Select
            label="Employee"
            value={employee}
            required
            onChange={(e) => setEmployee(e.target.value)}
          >
            <option value="">Choose employee</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.first_name} {p.last_name} · {p.employee_number}
              </option>
            ))}
          </Select>
        )}
        <Select label="Leave type" value={kind} required onChange={(e) => setKind(e.target.value)}>
          {types.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </Select>
        <TextField
          label="Start date"
          type="date"
          required
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <TextField
          label="End date"
          type="date"
          required
          min={start}
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
        <Toggle label="Half day at start" checked={halfStart} onCheckedChange={setHalfStart} />
        <Toggle label="Half day at end" checked={halfEnd} onCheckedChange={setHalfEnd} />
        <TextField
          label="Note (optional)"
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <p role="status" className="text-headline text-label">
          {ready
            ? `${days(preview.working_days)} working days`
            : "Choose dates to calculate working days."}
        </p>
        {ready &&
          preview.conflicts.map((w, i) => (
            <Alert key={i} tone={w.blocking ? "danger" : "warning"} title={w.message} />
          ))}
        <Button
          type="submit"
          loading={busy}
          disabled={!ready || preview.conflicts.some((w) => w.code === "EMPLOYEE_OVERLAP")}
        >
          Submit request
        </Button>
      </form>
    </SheetContent>
  );
}

export function DecisionSheet({ request, saved }: { request: LeaveRequest; saved: () => void }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/leave/approvals/{request_id}/preview", {
        params: { path: { request_id: request.id } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setPreview(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [request.id]);
  async function decide(approve: boolean) {
    setBusy(true);
    setProblem(null);
    const params = { path: { request_id: request.id } };
    const result = await attempt((c) =>
      approve
        ? c.POST("/leave/requests/{request_id}/approve", { params, body: { note } })
        : c.POST("/leave/requests/{request_id}/reject", { params, body: { note } }),
    );
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  return (
    <SheetContent
      title="Review leave request"
      description={`${request.employee_name} · ${request.leave_type_name}`}
    >
      <div className="flex flex-col gap-4">
        <p>
          {request.start_date} to {request.end_date} · {days(request.working_days)} days
        </p>
        {request.note && <p className="whitespace-pre-wrap break-words">{request.note}</p>}
        {problem && <Alert tone="danger" title={problem.message} />}
        {preview?.conflicts.map((w, i) => (
          <Alert key={i} tone={w.blocking ? "danger" : "warning"} title={w.message} />
        ))}
        <TextField
          label="Decision note (optional)"
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="flex gap-2">
          <Button variant="gray" loading={busy} onClick={() => void decide(false)}>
            Reject
          </Button>
          <Button
            loading={busy}
            disabled={!preview || preview.conflicts.some((w) => w.blocking)}
            onClick={() => void decide(true)}
          >
            Approve
          </Button>
        </div>
      </div>
    </SheetContent>
  );
}
