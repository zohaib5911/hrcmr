"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useCan } from "@/components/app/session-context";
import { SalarySection } from "@/components/employees/salary-section";
import { FormSheet } from "@/components/company/form-sheet";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { DatePicker } from "@/components/ui/date-picker";
import { Select } from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import { shortDate } from "@/lib/employees/profile";

type Schemas = components["schemas"];
export type EmploymentData = Schemas["EmploymentTab"];
type Call = Parameters<typeof attempt>[0];
type Kind = "responsibilities" | "previous_employment" | "education" | "training" | "memberships";
type RecordData = Record<string, string | number | null>;
type Field = { name: string; label: string; type?: "date" | "number" | "text" | "area" };
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const TYPES = [
  "full_time",
  "part_time",
  "fixed_term",
  "zero_hours",
  "casual",
  "apprentice",
  "agency",
] as const;
const label = (value: string) => value.replaceAll("_", " ");
const today = () => new Date().toISOString().slice(0, 10);
const SECTIONS: Record<Kind, { title: string; fields: Field[] }> = {
  responsibilities: {
    title: "Key responsibilities",
    fields: [
      { name: "text", label: "Responsibility", type: "area" },
      { name: "sort", label: "Sort order", type: "number" },
    ],
  },
  previous_employment: {
    title: "Previous employment",
    fields: [
      { name: "job_title", label: "Job title" },
      { name: "started_on", label: "Started on", type: "date" },
      { name: "left_on", label: "Left on", type: "date" },
      { name: "total_experience_years", label: "Total experience (years)", type: "number" },
      { name: "description", label: "Description", type: "area" },
    ],
  },
  education: {
    title: "Education",
    fields: [
      { name: "qualification", label: "Qualification" },
      { name: "subject", label: "Subject" },
      { name: "institution", label: "Institution" },
      { name: "awarding_body", label: "Awarding body" },
      { name: "year", label: "Year", type: "number" },
      { name: "percentage", label: "Percentage", type: "number" },
      { name: "grade", label: "Grade" },
    ],
  },
  training: {
    title: "Training",
    fields: [
      { name: "title", label: "Title" },
      { name: "started_on", label: "Started on", type: "date" },
      { name: "ended_on", label: "Ended on", type: "date" },
      { name: "description", label: "Description", type: "area" },
    ],
  },
  memberships: {
    title: "Certified memberships",
    fields: [
      { name: "licence_title", label: "Licence title" },
      { name: "licence_number", label: "Licence number" },
      { name: "started_on", label: "Started on", type: "date" },
      { name: "ended_on", label: "Ended on", type: "date" },
    ],
  },
};

/** Runs a call; on success toasts, refreshes the page data and closes. A problem stays in the sheet. */
function useSubmit(success: string, onClose: () => void) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  async function run(call: Call): Promise<Problem | null> {
    setBusy(true);
    setProblem(null);
    const outcome = await attempt(call);
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: success, tone: "success" });
      router.refresh();
      onClose();
      return null;
    }
    setProblem(outcome.problem);
    return outcome.problem;
  }
  return { busy, problem, setProblem, run };
}

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="bg-elevated rounded-card shadow-e1 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-headline text-label">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-caption text-label-secondary">{label}</dt>
          <dd className="text-body text-label break-words">
            {value === 0 ? 0 : value || <span className="text-label-secondary">Not set</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function EmploymentTab({ id, employment }: { id: string; employment: EmploymentData }) {
  const can = useCan();
  const mayEdit = can("employee.org_assignment.write");
  const [sheet, setSheet] = useState<
    "hire" | "role" | { kind: Kind; record: RecordData | null } | null
  >(null);
  const [lookups, setLookups] = useState<Lookups | null>(null);
  // ISS-17: the role editor's lists load when it opens, not with the read-only view; the
  // authorities are searched as you type (permission-scoped), never the whole directory.
  const editing = sheet === "role";
  useEffect(() => {
    if (!mayEdit || !editing || lookups) return;
    let active = true;
    async function load() {
      const [departments, designations, locations] = await Promise.all([
        attempt((c) => c.GET("/departments")),
        attempt((c) => c.GET("/designations")),
        attempt((c) => c.GET("/locations")),
      ]);
      if (active)
        setLookups({
          departments: departments.ok ? departments.data : [],
          designations: designations.ok ? designations.data : [],
          locations: locations.ok ? locations.data : [],
        });
    }
    void load();
    return () => {
      active = false;
    };
  }, [mayEdit, editing, lookups]);
  const current = employment.assignments.find(
    (a) => a.effective_from <= today() && (!a.ended_at || a.ended_at > today()),
  );
  const roleFacts = (role: Schemas["AssignmentOut"]): [string, ReactNode][] => [
    ["Department", role.department],
    ["Designation", role.designation],
    ["Location", role.location],
    ["Employment type", label(role.employment_type)],
    ["Effective from", shortDate(role.effective_from)],
    ["Reporting Authority", role.reporting_authority],
    ["Leave Sanctioning Authority", role.leave_sanctioning_authority],
    ["Working days", role.custom_working_days?.map(label).join(", ") ?? "Company working days"],
    ["Hours a day", role.hours_per_day],
  ];
  return (
    <div className="flex flex-col gap-6">
      <Section
        title="Hire date"
        action={
          mayEdit && (
            <Button variant="plain" size="sm" onClick={() => setSheet("hire")}>
              Edit hire date
            </Button>
          )
        }
      >
        <p className="text-body text-label">{shortDate(employment.hire_date)}</p>
      </Section>
      <Section
        title="Current role"
        action={
          mayEdit && (
            <Button variant="plain" size="sm" onClick={() => setSheet("role")}>
              Change role
            </Button>
          )
        }
      >
        {current ? (
          <Facts rows={roleFacts(current)} />
        ) : (
          <p className="text-body text-label-secondary">No role recorded.</p>
        )}
        {employment.assignments.length > 0 && (
          <details className="mt-4">
            <summary className="text-callout text-tint cursor-pointer">Role history</summary>
            <div className="mt-3 flex flex-col gap-4">
              {employment.assignments.map((a) => (
                <div key={a.id} className="border-separator border-t pt-3">
                  <p className="text-caption text-label-secondary mb-2">
                    {shortDate(a.effective_from)} ·{" "}
                    {a.ended_at
                      ? `Until ${shortDate(a.ended_at)}`
                      : a.effective_from > today()
                        ? "Scheduled"
                        : "Current"}
                  </p>
                  <Facts rows={roleFacts(a)} />
                </div>
              ))}
            </div>
          </details>
        )}
      </Section>
      <SalarySection id={id} hireDate={employment.hire_date} />
      {(Object.keys(SECTIONS) as Kind[]).map((kind) => {
        const config = SECTIONS[kind];
        const records =
          kind === "previous_employment"
            ? employment.previous_employment
              ? [employment.previous_employment]
              : []
            : employment[kind];
        return (
          <Section
            key={kind}
            title={config.title}
            action={
              mayEdit && (
                <Button
                  variant="plain"
                  size="sm"
                  onClick={() =>
                    setSheet({
                      kind,
                      record:
                        kind === "previous_employment" ? employment.previous_employment : null,
                    })
                  }
                >
                  {kind === "previous_employment" && employment.previous_employment
                    ? "Edit"
                    : "Add"}
                </Button>
              )
            }
          >
            {records.length === 0 ? (
              <p className="text-body text-label-secondary">Nothing recorded yet.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {records.map((record) => (
                  <div
                    key={record.id}
                    className="border-separator border-t pt-3 first:border-0 first:pt-0"
                  >
                    <Facts
                      rows={config.fields.map((f) => [f.label, (record as RecordData)[f.name]])}
                    />
                    {mayEdit && kind !== "previous_employment" && (
                      <Button variant="plain" size="sm" onClick={() => setSheet({ kind, record })}>
                        Edit
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>
        );
      })}
      {sheet === "hire" && (
        <HireDateSheet id={id} value={employment.hire_date} onClose={() => setSheet(null)} />
      )}
      {sheet === "role" && (
        <RoleSheet
          id={id}
          hireDate={employment.hire_date}
          current={employment.assignments[0]}
          lookups={lookups ?? EMPTY_LOOKUPS}
          onClose={() => setSheet(null)}
        />
      )}
      {sheet && typeof sheet === "object" && (
        <RecordSheet
          id={id}
          kind={sheet.kind}
          record={sheet.record}
          onClose={() => setSheet(null)}
        />
      )}
    </div>
  );
}

type AuthorityKey = "reporting_authority_employee_id" | "leave_sanctioning_employee_id";
type Lookups = {
  departments: Schemas["DepartmentOut"][];
  designations: Schemas["DesignationOut"][];
  locations: Schemas["LocationOut"][];
};
const EMPTY_LOOKUPS: Lookups = { departments: [], designations: [], locations: [] };

/** Eligible authorities by name or number, from the caller's permission-scoped directory. */
async function searchPeople(q: string, signal: AbortSignal, self: string) {
  const result = await attempt((c) => c.GET("/employees", { params: { query: { q } }, signal }));
  if (!result.ok) throw new Error(result.problem.message);
  return result.data.employees
    .filter((p) => p.id !== self)
    .slice(0, 50)
    .map((p) => ({
      value: p.id,
      label: `${p.first_name} ${p.last_name}`,
      description: p.employee_number,
    }));
}
function HireDateSheet({ id, value, onClose }: { id: string; value: string; onClose: () => void }) {
  const [date, setDate] = useState<string | null>(value);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string>();
  const { busy, problem, run } = useSubmit("Hire date saved", onClose);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!date || !reason.trim()) return setError("Choose a date and enter a reason.");
    setError(undefined);
    await run((c) =>
      c.PUT("/employees/{employee_id}/hire-date", {
        params: { path: { employee_id: id } },
        body: { hire_date: date, reason: reason.trim() },
      }),
    );
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Edit hire date"
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <DatePicker
        label="Hire date"
        name="hire_date"
        value={date}
        onChange={setDate}
        error={error}
      />
      <TextArea
        label="Reason"
        name="reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
    </FormSheet>
  );
}

function RoleSheet({
  id,
  hireDate,
  current,
  lookups,
  onClose,
}: {
  id: string;
  hireDate: string;
  current?: Schemas["AssignmentOut"];
  lookups: Lookups;
  onClose: () => void;
}) {
  const [form, setForm] = useState<Schemas["AssignmentIn"]>({
    employment_type: current?.employment_type ?? "full_time",
    effective_from: today() < hireDate ? hireDate : today(),
    department_id: current?.department_id,
    designation_id: current?.designation_id,
    location_id: current?.location_id,
    reporting_authority_employee_id: current?.reporting_authority_employee_id,
    leave_sanctioning_employee_id: current?.leave_sanctioning_employee_id,
    custom_working_days: current?.custom_working_days,
    hours_per_day: current?.hours_per_day,
  });
  const { busy, problem, run } = useSubmit("Role saved", onClose);
  const [error, setError] = useState<string>();
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((c) => ({ ...c, [key]: value }));
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form.effective_from) return setError("Choose an effective date.");
    await run((c) =>
      c.POST("/employees/{employee_id}/assignments", {
        params: { path: { employee_id: id } },
        body: form,
      }),
    );
  }
  // The current choices are shown by id with the names the assignment already carries.
  const [chosen, setChosen] = useState<Record<AuthorityKey, ComboboxOption | null>>(() => ({
    reporting_authority_employee_id: current?.reporting_authority_employee_id
      ? {
          value: current.reporting_authority_employee_id,
          label: current.reporting_authority ?? "Current authority",
        }
      : null,
    leave_sanctioning_employee_id: current?.leave_sanctioning_employee_id
      ? {
          value: current.leave_sanctioning_employee_id,
          label: current.leave_sanctioning_authority ?? "Current authority",
        }
      : null,
  }));
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Change role"
      description="The previous role is kept in history. Changes take effect on the date you choose."
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <Select
        label="Department"
        name="department_id"
        value={form.department_id ?? ""}
        onChange={(e) =>
          setForm((c) => ({ ...c, department_id: e.target.value || null, designation_id: null }))
        }
      >
        <option value="">Not set</option>
        {lookups.departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </Select>
      <Select
        label="Designation"
        name="designation_id"
        value={form.designation_id ?? ""}
        onChange={(e) => set("designation_id", e.target.value || null)}
      >
        <option value="">Not set</option>
        {lookups.designations
          .filter((d) => d.department_id === form.department_id)
          .map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
      </Select>
      <Select
        label="Location"
        name="location_id"
        value={form.location_id ?? ""}
        onChange={(e) => set("location_id", e.target.value || null)}
      >
        <option value="">Not set</option>
        {lookups.locations.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </Select>
      {(
        [
          ["reporting_authority_employee_id", "Reporting Authority"],
          ["leave_sanctioning_employee_id", "Leave Sanctioning Authority"],
        ] as const
      ).map(([key, title]) => (
        <Combobox
          key={key}
          label={title}
          name={key}
          hint="Type a name or employee number. Leave empty for none."
          value={chosen[key]}
          onChange={(option) => {
            setChosen((c) => ({ ...c, [key]: option }));
            set(key, option?.value ?? null);
          }}
          loadOptions={(q, signal) => searchPeople(q, signal, id)}
        />
      ))}
      <p className="text-caption text-label-secondary">
        Hierarchy levels will be available with the organogram.
      </p>
      <Select
        label="Employment type"
        name="employment_type"
        value={form.employment_type}
        onChange={(e) => set("employment_type", e.target.value as typeof form.employment_type)}
      >
        {TYPES.map((t) => (
          <option key={t} value={t}>
            {label(t)}
          </option>
        ))}
      </Select>
      <Toggle
        label="Works different days from the company"
        checked={form.custom_working_days != null}
        onCheckedChange={(checked) =>
          set("custom_working_days", checked ? ["mon", "tue", "wed", "thu", "fri"] : null)
        }
      />
      {form.custom_working_days != null && (
        <fieldset>
          <legend className="text-callout text-label mb-2">Working days</legend>
          <div className="flex flex-wrap gap-3">
            {DAYS.map((day) => (
              <label key={day} className="text-callout text-label flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.custom_working_days?.includes(day) ?? false}
                  onChange={(e) =>
                    set(
                      "custom_working_days",
                      e.target.checked
                        ? [...(form.custom_working_days ?? []), day]
                        : form.custom_working_days?.filter((d) => d !== day),
                    )
                  }
                />
                {label(day)}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <TextField
        label="Hours a day"
        name="hours_per_day"
        type="number"
        value={form.hours_per_day ?? ""}
        onChange={(e) => set("hours_per_day", e.target.value || null)}
      />
      <DatePicker
        label="Effective from"
        name="effective_from"
        min={hireDate}
        value={form.effective_from}
        onChange={(v) => set("effective_from", v ?? "")}
        error={error}
      />
    </FormSheet>
  );
}

function RecordSheet({
  id,
  kind,
  record,
  onClose,
}: {
  id: string;
  kind: Kind;
  record: RecordData | null;
  onClose: () => void;
}) {
  const config = SECTIONS[kind];
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      config.fields.map((f) => [f.name, String(record?.[f.name] ?? (f.name === "sort" ? 0 : ""))]),
    ),
  );
  const { busy, problem, run } = useSubmit("Record saved", onClose);
  const set = (key: string, value: string) => setForm((c) => ({ ...c, [key]: value }));
  async function save(event: FormEvent) {
    event.preventDefault();
    const body = Object.fromEntries(
      config.fields.map((f) => [
        f.name,
        f.type === "number"
          ? form[f.name]
            ? Number(form[f.name])
            : null
          : (form[f.name] ?? "").trim() || null,
      ]),
    );
    const params = { path: { employee_id: id, record_id: String(record?.id ?? "") } };
    switch (kind) {
      case "responsibilities":
        await run((c) =>
          record
            ? c.PUT("/employees/{employee_id}/responsibilities/{record_id}", {
                params,
                body: body as Schemas["ResponsibilityIn"],
              })
            : c.POST("/employees/{employee_id}/responsibilities", {
                params,
                body: body as Schemas["ResponsibilityIn"],
              }),
        );
        break;
      case "education":
        await run((c) =>
          record
            ? c.PUT("/employees/{employee_id}/education/{record_id}", {
                params,
                body: body as Schemas["EducationIn"],
              })
            : c.POST("/employees/{employee_id}/education", {
                params,
                body: body as Schemas["EducationIn"],
              }),
        );
        break;
      case "training":
        await run((c) =>
          record
            ? c.PUT("/employees/{employee_id}/training/{record_id}", {
                params,
                body: body as Schemas["TrainingIn"],
              })
            : c.POST("/employees/{employee_id}/training", {
                params,
                body: body as Schemas["TrainingIn"],
              }),
        );
        break;
      case "memberships":
        await run((c) =>
          record
            ? c.PUT("/employees/{employee_id}/memberships/{record_id}", {
                params,
                body: body as Schemas["MembershipIn"],
              })
            : c.POST("/employees/{employee_id}/memberships", {
                params,
                body: body as Schemas["MembershipIn"],
              }),
        );
        break;
      case "previous_employment":
        await run((c) => c.PUT("/employees/{employee_id}/previous-employment", { params, body }));
        break;
    }
  }
  async function remove() {
    const params = { path: { employee_id: id, record_id: String(record?.id) } };
    switch (kind) {
      case "responsibilities":
        await run((c) =>
          c.DELETE("/employees/{employee_id}/responsibilities/{record_id}", { params }),
        );
        break;
      case "education":
        await run((c) => c.DELETE("/employees/{employee_id}/education/{record_id}", { params }));
        break;
      case "training":
        await run((c) => c.DELETE("/employees/{employee_id}/training/{record_id}", { params }));
        break;
      case "memberships":
        await run((c) => c.DELETE("/employees/{employee_id}/memberships/{record_id}", { params }));
        break;
    }
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={`${record ? "Edit" : "Add"} ${config.title.toLowerCase()}`}
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(record && kind !== "previous_employment"
        ? {
            archive: {
              label: "Remove",
              question: "Remove this record?",
              detail: "This change is recorded in the audit trail.",
              onConfirm: remove,
            },
          }
        : {})}
    >
      {config.fields.map((field) =>
        field.type === "date" ? (
          <DatePicker
            key={field.name}
            label={field.label}
            name={field.name}
            value={form[field.name] || null}
            onChange={(v) => set(field.name, v ?? "")}
          />
        ) : field.type === "area" ? (
          <TextArea
            key={field.name}
            label={field.label}
            name={field.name}
            value={form[field.name]}
            onChange={(e) => set(field.name, e.target.value)}
          />
        ) : (
          <TextField
            key={field.name}
            label={field.label}
            name={field.name}
            type={field.type === "number" ? "number" : "text"}
            value={form[field.name]}
            onChange={(e) => set(field.name, e.target.value)}
          />
        ),
      )}
    </FormSheet>
  );
}
