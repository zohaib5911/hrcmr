"use client";

import { CalendarClock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Shift = components["schemas"]["ShiftTypeOut"];
type Late = components["schemas"]["LatePolicyOut"];
type Off = components["schemas"]["DayOffPatternOut"];
type Department = components["schemas"]["DepartmentOut"];
type Designation = components["schemas"]["DesignationOut"];
type Tab = "shift" | "late" | "off";
type Row = { id: string; title: string; detail: string; value: Shift | Late | Off };
const LABEL: Record<Tab, string> = {
  shift: "Shift type",
  late: "Late policy",
  off: "Day off pattern",
};
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const NAMES = ["Morning", "Afternoon", "Evening", "Night", "Early", "Late", "Day", "Weekend"];

export function RotaSettings() {
  const can = useCan();
  const shiftRead = can("rota.shift.read"),
    lateRead = can("rota.late_policy.read"),
    offRead = can("rota.day_off.read");
  const [tab, setTab] = useState<Tab>("shift");
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [late, setLate] = useState<Late[]>([]);
  const [off, setOff] = useState<Off[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [version, setVersion] = useState(0);
  const [opened, setOpened] = useState<{ row: Row | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const canDepartments = can("company.department.read"),
    canDesignations = can("settings.designation.read");
  useEffect(() => {
    let active = true;
    void Promise.all([
      shiftRead ? attempt((c) => c.GET("/rota/shift-types")) : null,
      lateRead ? attempt((c) => c.GET("/rota/late-policies")) : null,
      offRead ? attempt((c) => c.GET("/rota/day-off-patterns")) : null,
      canDepartments ? attempt((c) => c.GET("/departments")) : null,
      canDesignations ? attempt((c) => c.GET("/designations")) : null,
    ]).then(([s, l, o, d, j]) => {
      if (!active) return;
      setLoaded(true);
      if (s?.ok) setShifts(s.data);
      if (l?.ok) setLate(l.data);
      if (o?.ok) setOff(o.data);
      if (d?.ok) setDepartments(d.data);
      if (j?.ok) setDesignations(j.data);
      const failed = [s, l, o, d, j].find((result) => result && !result.ok);
      if (failed && !failed.ok) setProblem(failed.problem);
      else setProblem(null);
    });
    return () => {
      active = false;
    };
  }, [version, shiftRead, lateRead, offRead, canDepartments, canDesignations]);
  const writable = can(
    tab === "shift"
      ? "rota.shift.write"
      : tab === "late"
        ? "rota.late_policy.write"
        : "rota.day_off.write",
  );
  const scopeName = (r: Late | Off) =>
    `${departments.find((d) => d.id === r.department_id)?.name ?? "Archived department"} · ${designations.find((d) => d.id === r.designation_id)?.title ?? "Archived designation"} · ${shifts.find((s) => s.id === r.shift_type_id)?.name ?? "Archived shift"}`;
  const rows: Row[] =
    tab === "shift"
      ? shifts.map((s) => ({
          id: s.id,
          title: s.name,
          detail: `${s.starts_at.slice(0, 5)} to ${s.ends_at.slice(0, 5)}${s.description ? ` · ${s.description}` : ""}`,
          value: s,
        }))
      : tab === "late"
        ? late.map((l) => ({
            id: l.id,
            title: scopeName(l),
            detail: `${l.grace_minutes} minute grace · ${l.allowed_late_days_per_month} late days/month · ${l.deduction_type.replaceAll("_", " ")}${l.deduction_type === "none" ? "" : `: ${l.deduction_value}`}`,
            value: l,
          }))
        : off.map((o) => ({
            id: o.id,
            title: scopeName(o),
            detail: `${o.weekdays_off.map((d) => DAYS[d - 1]).join(", ") || "No weekdays off"} · ${o.works_public_holidays ? "Works public holidays" : "Public holidays off"}`,
            value: o,
          }));
  async function archive(row: Row) {
    setBusy(true);
    setProblem(null);
    const params = { params: { path: { setting_id: row.id } } };
    const result = await (tab === "shift"
      ? attempt((c) => c.DELETE("/rota/shift-types/{setting_id}", params))
      : tab === "late"
        ? attempt((c) => c.DELETE("/rota/late-policies/{setting_id}", params))
        : attempt((c) => c.DELETE("/rota/day-off-patterns/{setting_id}", params)));
    setBusy(false);
    if (result.ok) setVersion((v) => v + 1);
    else setProblem(result.problem);
  }
  const columns: Column<Row>[] = [
    { id: "name", header: "Setting", primary: true, cell: (r) => r.title },
    {
      id: "detail",
      header: "Details",
      cell: (r) => <span className="whitespace-pre-wrap break-words">{r.detail}</span>,
    },
    {
      id: "edit",
      header: "Open",
      cell: (r) => (
        <Button
          variant="gray"
          size="sm"
          className="h-auto min-h-11 whitespace-normal"
          onClick={() => setOpened({ row: r })}
        >
          {writable ? "Edit" : "View"} {r.title}
        </Button>
      ),
    },
    {
      id: "archive",
      header: "Archive",
      cell: (r) => (
        <div className="[&_button]:h-auto [&_button]:min-h-11 [&_button]:whitespace-normal">
          <InlineConfirm
            label={`Archive ${r.title}`}
            prompt={`Archive ${r.title}?`}
            confirmLabel="Archive setting"
            destructive
            disabled={busy}
            onConfirm={() => archive(r)}
          />
        </div>
      ),
    },
  ];
  const prerequisites =
    !!shifts.length && designations.some((j) => departments.some((d) => d.id === j.department_id));
  const segments = [
    { value: "shift" as const, label: "Shift types", allowed: shiftRead },
    { value: "late" as const, label: "Late policy", allowed: lateRead },
    { value: "off" as const, label: "Day off patterns", allowed: offRead },
  ].filter((s) => s.allowed);
  return (
    <>
      <PageHeader
        title="Rota settings"
        description="Shift templates, late policies and regular days off."
        actions={
          <Button asChild variant="gray">
            <Link href="/rota">Rota</Link>
          </Button>
        }
      />
      <div className="flex flex-col gap-5">
        {segments.length ? (
          <div className="overflow-x-auto">
            <SegmentedControl
              label="Rota setting"
              value={tab}
              onValueChange={(value) => {
                setTab(value);
                setProblem(null);
              }}
              segments={segments}
            />
          </div>
        ) : (
          <Alert title="You do not have permission to view rota settings." />
        )}
        {problem && !opened && <Alert tone="danger" title={problem.message} />}
        {!loaded ? (
          <p role="status">Loading rota settings…</p>
        ) : tab !== "shift" && !prerequisites ? (
          <EmptyState
            icon={CalendarClock}
            title="Set up a department, designation and shift first"
            description="Late policies and day off patterns apply to a designation in a department and one shift type."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button asChild variant="gray">
                  <Link href="/company/departments">Departments</Link>
                </Button>
                <Button asChild variant="gray">
                  <Link href="/company/designations">Designations</Link>
                </Button>
                <Button variant="gray" onClick={() => setTab("shift")}>
                  Shift types
                </Button>
              </div>
            }
          />
        ) : (
          <>
            {writable && (
              <div>
                <Button onClick={() => setOpened({ row: null })}>
                  Add {LABEL[tab].toLowerCase()}
                </Button>
              </div>
            )}
            <DataTable
              caption={
                tab === "shift"
                  ? "Shift types"
                  : tab === "late"
                    ? "Late policies"
                    : "Day off patterns"
              }
              columns={writable ? columns : columns.filter((column) => column.id !== "archive")}
              rows={rows}
              getRowId={(r) => r.id}
              onRowOpen={(row) => setOpened({ row })}
            />
          </>
        )}
      </div>
      <Sheet
        open={opened !== null}
        onOpenChange={(open) => {
          if (!open) {
            setOpened(null);
            setProblem(null);
          }
        }}
      >
        {opened && (
          <SettingForm
            key={`${tab}:${opened.row?.id ?? "new"}`}
            tab={tab}
            row={opened.row}
            writable={writable}
            departments={departments}
            designations={designations}
            shifts={shifts}
            close={() => setOpened(null)}
            saved={() => {
              setOpened(null);
              setVersion((v) => v + 1);
            }}
          />
        )}
      </Sheet>
    </>
  );
}

function SettingForm({
  tab,
  row,
  writable,
  departments,
  designations,
  shifts,
  close,
  saved,
}: {
  tab: Tab;
  row: Row | null;
  writable: boolean;
  departments: Department[];
  designations: Designation[];
  shifts: Shift[];
  close: () => void;
  saved: () => void;
}) {
  const shift = tab === "shift" ? (row?.value as Shift | undefined) : undefined;
  const scoped = tab !== "shift" ? (row?.value as Late | Off | undefined) : undefined;
  const late = tab === "late" ? (row?.value as Late | undefined) : undefined;
  const off = tab === "off" ? (row?.value as Off | undefined) : undefined;
  const [name, setName] = useState(shift?.name ?? "");
  const [description, setDescription] = useState(shift?.description ?? "");
  const [start, setStart] = useState(shift?.starts_at.slice(0, 5) ?? "09:00");
  const [end, setEnd] = useState(shift?.ends_at.slice(0, 5) ?? "17:00");
  const [breakStart, setBreakStart] = useState(shift?.break_start?.slice(0, 5) ?? "");
  const [breakEnd, setBreakEnd] = useState(shift?.break_end?.slice(0, 5) ?? "");
  const [colour, setColour] = useState(shift?.colour ?? "#007aff");
  const [department, setDepartment] = useState(scoped?.department_id ?? "");
  const [designation, setDesignation] = useState(scoped?.designation_id ?? "");
  const [shiftId, setShiftId] = useState(scoped?.shift_type_id ?? "");
  const [grace, setGrace] = useState(String(late?.grace_minutes ?? 5));
  const [allowed, setAllowed] = useState(String(late?.allowed_late_days_per_month ?? 0));
  const [deduction, setDeduction] = useState<Late["deduction_type"]>(
    late?.deduction_type ?? "none",
  );
  const [value, setValue] = useState(String(late?.deduction_value ?? "0"));
  const [days, setDays] = useState<number[]>(off?.weekdays_off ?? [6, 7]);
  const [holidays, setHolidays] = useState(off?.works_public_holidays ?? false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const title = `${writable ? (row ? "Edit" : "Add") : "View"} ${LABEL[tab].toLowerCase()}`;
  async function save() {
    setBusy(true);
    setProblem(null);
    const scope = {
      department_id: department,
      designation_id: designation,
      shift_type_id: shiftId,
    };
    const shiftBody = {
      name,
      description: description.trim() || null,
      starts_at: start,
      ends_at: end,
      break_start: breakStart || null,
      break_end: breakEnd || null,
      colour,
    };
    const lateBody = {
      ...scope,
      grace_minutes: Number(grace),
      allowed_late_days_per_month: Number(allowed),
      deduction_type: deduction,
      deduction_value: deduction === "none" ? "0" : value,
    };
    const offBody = { ...scope, weekdays_off: days, works_public_holidays: holidays };
    const path = { path: { setting_id: row?.id ?? "" } };
    const result = await (tab === "shift"
      ? row
        ? attempt((c) => c.PUT("/rota/shift-types/{setting_id}", { params: path, body: shiftBody }))
        : attempt((c) => c.POST("/rota/shift-types", { body: shiftBody }))
      : tab === "late"
        ? row
          ? attempt((c) =>
              c.PUT("/rota/late-policies/{setting_id}", { params: path, body: lateBody }),
            )
          : attempt((c) => c.POST("/rota/late-policies", { body: lateBody }))
        : row
          ? attempt((c) =>
              c.PUT("/rota/day-off-patterns/{setting_id}", { params: path, body: offBody }),
            )
          : attempt((c) => c.POST("/rota/day-off-patterns", { body: offBody })));
    setBusy(false);
    if (result.ok) saved();
    else setProblem(result.problem);
  }
  function mins(t: string) {
    const [h, m] = t.split(":").map(Number);
    return (h ?? 0) * 60 + (m ?? 0);
  }
  const duration = start && end ? (mins(end) - mins(start) + 1440) % 1440 : 0;
  const breakMinutes =
    breakStart && breakEnd ? (mins(breakEnd) - mins(breakStart) + 1440) % 1440 : 0;
  return (
    <SheetContent
      title={title}
      readOnly={!writable}
      footer={
        <>
          <Button variant="gray" onClick={close} disabled={busy}>
            Close
          </Button>
          {writable && (
            <Button type="submit" form="rota-setting" loading={busy}>
              Save {LABEL[tab].toLowerCase()}
            </Button>
          )}
        </>
      }
    >
      <form
        id="rota-setting"
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        {problem && <Alert tone="danger" title={problem.message} />}
        <fieldset disabled={busy || !writable} className="flex min-w-0 flex-col gap-4">
          {tab === "shift" ? (
            <>
              <TextField
                label="Shift name"
                required
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <div className="flex flex-wrap gap-2" role="group" aria-label="Suggested shift names">
                {NAMES.map((n) => (
                  <Button key={n} size="sm" variant="gray" onClick={() => setName(n)}>
                    {n}
                  </Button>
                ))}
              </div>
              <TextArea
                label="Description (optional)"
                maxLength={2000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="Starts"
                  type="time"
                  required
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
                <TextField
                  label="Finishes"
                  type="time"
                  required
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="Break starts (optional)"
                  type="time"
                  value={breakStart}
                  onChange={(e) => setBreakStart(e.target.value)}
                />
                <TextField
                  label="Break finishes (optional)"
                  type="time"
                  value={breakEnd}
                  onChange={(e) => setBreakEnd(e.target.value)}
                />
              </div>
              <p role="status">
                {((duration - breakMinutes) / 60).toFixed(2)} hours paid · An earlier finish is the
                next day.
              </p>
              <Select
                label="Shift colour"
                value={colour}
                onChange={(e) => setColour(e.target.value)}
              >
                {[
                  ["#007aff", "Blue"],
                  ["#34c759", "Green"],
                  ["#ff9500", "Orange"],
                  ["#af52de", "Purple"],
                  ["#30b0c7", "Teal"],
                ].map(([v, label]) => (
                  <option key={v} value={v}>
                    {label}
                  </option>
                ))}
              </Select>
            </>
          ) : (
            <>
              <Select
                label="Department"
                required
                value={department}
                onChange={(e) => {
                  setDepartment(e.target.value);
                  setDesignation("");
                }}
              >
                <option value="">Choose a department</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
              <Select
                label="Designation"
                required
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
              >
                <option value="">Choose a designation</option>
                {designations
                  .filter((d) => d.department_id === department)
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title}
                    </option>
                  ))}
              </Select>
              <Select
                label="Shift type"
                required
                value={shiftId}
                onChange={(e) => setShiftId(e.target.value)}
              >
                <option value="">Choose a shift</option>
                {shifts.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
              {tab === "late" ? (
                <>
                  <TextField
                    label="Grace minutes"
                    type="number"
                    min={0}
                    max={1440}
                    required
                    value={grace}
                    onChange={(e) => setGrace(e.target.value)}
                  />
                  <TextField
                    label="Allowed late days per month"
                    type="number"
                    min={0}
                    max={31}
                    required
                    value={allowed}
                    onChange={(e) => setAllowed(e.target.value)}
                  />
                  <Select
                    label="Deduction type"
                    value={deduction}
                    onChange={(e) => setDeduction(e.target.value as Late["deduction_type"])}
                  >
                    <option value="none">None</option>
                    <option value="fixed">Fixed amount</option>
                    <option value="percentage_of_day">Percentage of day</option>
                  </Select>
                  {deduction !== "none" && (
                    <TextField
                      label={deduction === "fixed" ? "Deduction amount" : "Deduction percentage"}
                      type="number"
                      min={0}
                      max={deduction === "percentage_of_day" ? 100 : 99999999.99}
                      step="0.01"
                      required
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                    />
                  )}
                </>
              ) : (
                <>
                  <fieldset className="flex flex-col gap-3">
                    <legend className="text-headline mb-2">Weekdays off</legend>
                    {DAYS.map((day, i) => (
                      <Checkbox
                        key={day}
                        label={day}
                        checked={days.includes(i + 1)}
                        onCheckedChange={(checked) =>
                          setDays((old) =>
                            checked ? [...old, i + 1] : old.filter((v) => v !== i + 1),
                          )
                        }
                      />
                    ))}
                  </fieldset>
                  <Toggle
                    label="Works public holidays"
                    checked={holidays}
                    onCheckedChange={setHolidays}
                  />
                </>
              )}
            </>
          )}
        </fieldset>
      </form>
    </SheetContent>
  );
}
