"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { DatePicker } from "@/components/ui/date-picker";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import {
  CHANGE_TYPES,
  ORG_CHANGE_TYPES,
  SPONSOR_GUIDANCE,
  SPONSOR_GLOSSARY,
  CHECKED_ON,
  type Reporting,
  type OrgChange,
} from "@/lib/compliance/changes";
import { documentLabel, DOCUMENT_STATUS } from "@/lib/compliance/sponsor-documents";
import { shortDate } from "@/lib/employees/profile";

type Schemas = components["schemas"];
const today = () => new Date().toISOString().slice(0, 10);
const EMPLOYMENT_TYPES = [
  "full_time",
  "part_time",
  "fixed_term",
  "zero_hours",
  "casual",
  "apprentice",
  "agency",
] as const;
type Saved = { onSaved: () => void; onClose: () => void };

export function ReportingSources() {
  return (
    <p className="text-caption text-label-secondary">
      General guidance, not legal advice.{" "}
      <a className="text-tint underline" href={SPONSOR_GUIDANCE} target="_blank" rel="noreferrer">
        Sponsor reporting guidance
      </a>{" "}
      ·{" "}
      <a className="text-tint underline" href={SPONSOR_GLOSSARY} target="_blank" rel="noreferrer">
        Working-day definition
      </a>{" "}
      ·{" "}
      <a
        className="text-tint underline"
        href="https://www.gov.uk/bank-holidays"
        target="_blank"
        rel="noreferrer"
      >
        Bank holidays
      </a>
      . Sources checked {CHECKED_ON}.
    </p>
  );
}

function DeadlinePreview({
  date,
  kind,
}: {
  date: string | null;
  kind: "worker" | "organisation" | "prompt";
}) {
  const [result, setResult] = useState<{
    key: string;
    data?: Schemas["DeadlineOut"];
    problem?: Problem;
  } | null>(null);
  const key = (date ?? "") + kind;
  useEffect(() => {
    let active = true;
    async function load() {
      if (!date) return;
      const result = await attempt((c) =>
        c.GET("/compliance/reporting-deadline", { params: { query: { change_date: date, kind } } }),
      );
      if (active)
        setResult(result.ok ? { key, data: result.data } : { key, problem: result.problem });
    }
    void load();
    return () => {
      active = false;
    };
  }, [date, kind, key]);
  if (!date)
    return (
      <p className="text-callout text-label-secondary">
        Choose the event date to calculate the reporting target.
      </p>
    );
  if (!result || result.key !== key)
    return (
      <p role="status" className="text-callout text-label-secondary">
        Calculating reporting target…
      </p>
    );
  if (result.problem) return <Alert tone="warning" title={result.problem.message} />;
  return (
    <Alert
      tone={kind === "prompt" ? "warning" : "info"}
      title={
        result.data?.deadline_date
          ? "Reporting deadline: " + shortDate(result.data.deadline_date)
          : "Report promptly"
      }
    >
      {kind === "prompt"
        ? "AO and Key Contact replacements are excluded from the standard 20-working-day rule. Check the official guidance."
        : `${kind === "worker" ? 10 : 20} working days after this date, excluding weekends and bank holidays for ${result.data?.calendar_region.replaceAll("-", " ")}.`}
    </Alert>
  );
}

export function EmployeeChangeSheet({
  employeeId,
  onClose,
  onSaved,
}: { employeeId?: string } & Saved) {
  const toast = useToast();
  const [id, setId] = useState(employeeId ?? "");
  const [people, setPeople] = useState<Schemas["EmployeeRow"][]>([]);
  const [loadedId, setLoadedId] = useState("");
  const [defaults, setDefaults] = useState<Schemas["ChangeDefaults"] | null>(null);
  const [form, setForm] = useState({
    change_type: "other" as Schemas["ChangeIn"]["change_type"],
    change_date: today() as string | null,
    employment_type: "" as NonNullable<Schemas["ChangeIn"]["employment_type"]> | "",
    job_title: "",
    nationality: "",
    contact_number: "",
    address: "",
    remarks: "",
    ack_inform_hr: false,
    ack_home_office_interview: false,
    documents_snapshot: [] as string[],
  });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((c) => ({ ...c, [key]: value }));
  useEffect(() => {
    if (employeeId) return;
    let active = true;
    async function load() {
      const result = await attempt((c) => c.GET("/employees"));
      if (!active) return;
      if (result.ok) setPeople(result.data.employees);
      else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [employeeId]);
  useEffect(() => {
    let active = true;
    async function load() {
      if (!id) return;
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/changes/options", {
          params: { path: { employee_id: id } },
        }),
      );
      if (!active) return;
      if (!result.ok) return setProblem(result.problem);
      const d = result.data;
      setDefaults(d);
      setLoadedId(id);
      setProblem(null);
      setForm((f) => ({
        ...f,
        employment_type: d.employment_type ?? "",
        job_title: d.job_title ?? "",
        nationality: d.nationality ?? "",
        contact_number: d.contact_number ?? "",
        address: d.address ?? "",
        documents_snapshot: [],
      }));
    }
    void load();
    return () => {
      active = false;
    };
  }, [id]);
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setProblem(null);
    if (!id || id !== loadedId)
      return setError("Choose the employee and wait for their current details.");
    if (!form.change_date) return setError("Choose the reportable event date.");
    setBusy(true);
    const body: Schemas["ChangeIn"] = {
      ...form,
      change_date: form.change_date,
      employment_type: form.employment_type || null,
      job_title: form.job_title.trim() || null,
      nationality: form.nationality.trim() || null,
      contact_number: form.contact_number.trim() || null,
      address: form.address.trim() || null,
      remarks: form.remarks.trim() || null,
    };
    const result = await attempt((c) =>
      c.POST("/employees/{employee_id}/changes", { params: { path: { employee_id: id } }, body }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Change logged", tone: "success" });
      onSaved();
      onClose();
    } else setProblem(result.problem);
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Log a change"
      description="Save the reportable event and a snapshot of the details and document versions that apply."
      busy={busy}
      problem={problem}
      onSubmit={save}
    >
      {!employeeId && (
        <Select
          label="Employee"
          name="employee_id"
          value={id}
          onChange={(e) => setId(e.target.value)}
        >
          <option value="">Choose an employee</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.first_name} {p.last_name} · {p.employee_number}
            </option>
          ))}
        </Select>
      )}
      <Select
        label="Change type"
        name="change_type"
        value={form.change_type}
        onChange={(e) => set("change_type", e.target.value as typeof form.change_type)}
      >
        {CHANGE_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </Select>
      <DatePicker
        label="Reportable event date"
        name="change_date"
        value={form.change_date}
        max={today()}
        onChange={(v) => set("change_date", v)}
        hint={
          form.change_type === "unauthorised_absence"
            ? "Use the 10th working day of the unauthorised absence, not the first day of absence."
            : form.change_type === "did_not_start"
              ? "Use the date the start-delay period ends under the official guidance, rather than assuming the planned start date."
              : "The 10-working-day reporting period starts after this date."
        }
      />
      <DeadlinePreview date={form.change_date} kind="worker" />
      {id && id !== loadedId && (
        <p role="status" className="text-callout text-label-secondary">
          Loading current details…
        </p>
      )}
      <Select
        label="Employment type"
        name="employment_type"
        value={form.employment_type}
        onChange={(e) => set("employment_type", e.target.value as typeof form.employment_type)}
      >
        <option value="">Not set</option>
        {EMPLOYMENT_TYPES.map((t) => (
          <option key={t} value={t}>
            {t.replaceAll("_", " ")}
          </option>
        ))}
      </Select>
      <TextField
        label="Job title"
        name="job_title"
        value={form.job_title}
        onChange={(e) => set("job_title", e.target.value)}
        maxLength={160}
      />
      <TextField
        label="Nationality"
        name="nationality"
        value={form.nationality}
        onChange={(e) => set("nationality", e.target.value)}
        maxLength={80}
      />
      <TextField
        label="Contact number"
        name="contact_number"
        value={form.contact_number}
        onChange={(e) => set("contact_number", e.target.value)}
        maxLength={40}
      />
      <TextArea
        label="Address"
        name="address"
        value={form.address}
        onChange={(e) => set("address", e.target.value)}
        maxLength={2000}
      />
      <TextArea
        label="Remarks or restriction to work"
        name="remarks"
        value={form.remarks}
        onChange={(e) => set("remarks", e.target.value)}
        maxLength={2000}
      />
      <Checkbox
        label="Employee told to inform HR promptly"
        checked={form.ack_inform_hr}
        onCheckedChange={(v) => set("ack_inform_hr", v === true)}
      />
      <Checkbox
        label="Employee told to cooperate with a Home Office interview"
        checked={form.ack_home_office_interview}
        onCheckedChange={(v) => set("ack_home_office_interview", v === true)}
      />
      <fieldset className="flex flex-col gap-3">
        <legend className="text-callout text-label mb-2">Current documents that apply</legend>
        {loadedId === id &&
          defaults?.documents.map((d) => (
            <Checkbox
              key={d.id}
              label={documentLabel(d.doc_type) + " · version " + d.version}
              description={DOCUMENT_STATUS[d.status].label}
              checked={form.documents_snapshot.includes(d.id)}
              onCheckedChange={(v) =>
                set(
                  "documents_snapshot",
                  v === true
                    ? [...form.documents_snapshot, d.id]
                    : form.documents_snapshot.filter((value) => value !== d.id),
                )
              }
            />
          ))}
        {loadedId === id && defaults?.documents.length === 0 && (
          <p className="text-callout text-label-secondary">
            No current sponsor documents recorded.
          </p>
        )}
      </fieldset>
      <ReportingSources />
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}

export function ReportedSheet({ record, onClose, onSaved }: { record: Reporting } & Saved) {
  const toast = useToast();
  const [date, setDate] = useState<string | null>(today());
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setProblem(null);
    if (!date || !reference.trim())
      return setError("Choose the reporting date and enter the SMS reference.");
    setBusy(true);
    const body = { reported_date: date, reference: reference.trim() };
    const result = await attempt<Reporting>((c) =>
      "employee_id" in record
        ? c.POST("/changes/{change_id}/mark-reported", {
            params: { path: { change_id: record.id } },
            body,
          })
        : c.POST("/compliance/org-changes/{change_id}/mark-reported", {
            params: { path: { change_id: record.id } },
            body,
          }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Reporting recorded", tone: "success" });
      onSaved();
      onClose();
    } else setProblem(result.problem);
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Mark as reported"
      description="Record the report you already made in SMS. Your name and the time you record it are kept in the audit trail."
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <DatePicker
        label="Date reported in SMS"
        name="reported_date"
        value={date}
        min={record.change_date}
        max={today()}
        onChange={setDate}
      />
      <TextField
        label="SMS reference"
        name="reference"
        value={reference}
        onChange={(e) => setReference(e.target.value)}
        maxLength={160}
      />
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}

export function OrgChangeSheet({ record, onClose, onSaved }: { record: OrgChange | null } & Saved) {
  const toast = useToast();
  const [kind, setKind] = useState<Schemas["OrgChangeIn"]["change_type"]>(
    record?.change_type ?? "address",
  );
  const [date, setDate] = useState<string | null>(record?.change_date ?? today());
  const [remarks, setRemarks] = useState(record?.remarks ?? "");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setProblem(null);
    if (!date) return setError("Choose the date the organisation became aware.");
    setBusy(true);
    const body = { change_type: kind, change_date: date, remarks: remarks.trim() || null };
    const result = await attempt((c) =>
      record
        ? c.PUT("/compliance/org-changes/{change_id}", {
            params: { path: { change_id: record.id } },
            body,
          })
        : c.POST("/compliance/org-changes", { body }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({
        title: record ? "Organisation entry updated" : "Organisation change logged",
        tone: "success",
      });
      onSaved();
      onClose();
    } else setProblem(result.problem);
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={record ? "Edit organisation change" : "Log organisation change"}
      description="Record when the organisation became aware of the change."
      busy={busy}
      problem={problem}
      onSubmit={save}
    >
      <Select
        label="Organisation change type"
        name="change_type"
        value={kind}
        onChange={(e) => setKind(e.target.value as typeof kind)}
      >
        {ORG_CHANGE_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </Select>
      <DatePicker
        label="Date organisation became aware"
        name="change_date"
        value={date}
        max={today()}
        onChange={setDate}
      />
      <DeadlinePreview
        date={date}
        kind={kind === "ao_or_key_contact" ? "prompt" : "organisation"}
      />
      <TextArea
        label="Remarks"
        name="remarks"
        value={remarks}
        onChange={(e) => setRemarks(e.target.value)}
        maxLength={2000}
      />
      <ReportingSources />
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}

export function ArchiveChangeSheet({ record, onClose, onSaved }: { record: OrgChange } & Saved) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    if (!reason.trim()) return setError("Enter why this entry should be archived.");
    setBusy(true);
    const result = await attempt((c) =>
      c.DELETE("/compliance/org-changes/{change_id}", {
        params: { path: { change_id: record.id } },
        body: { reason: reason.trim() },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Organisation entry archived", tone: "success" });
      onSaved();
      onClose();
    } else setProblem(result.problem);
  }
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Archive organisation entry"
      description="Use this for an entry made by mistake. It stays in the audit record with your reason."
      onSubmit={save}
      busy={busy}
      problem={problem}
      saveLabel="Archive entry"
    >
      <TextArea
        label="Reason for archiving"
        name="reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={1000}
      />
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}
