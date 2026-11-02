"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useCan, useMe } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { RTWChip } from "@/components/employees/rtw-chip";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import { CHECK_TYPES } from "@/lib/employees/rtw";
import { shortDate } from "@/lib/employees/profile";

type Schemas = components["schemas"];
type Check = Schemas["CheckOut"];
type Tab = Schemas["RTWTab"];
const today = () => new Date().toISOString().slice(0, 10);

export function RTWTab({ id, onChanged }: { id: string; onChanged: () => void }) {
  const can = useCan();
  const [data, setData] = useState<Tab | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sheet, setSheet] = useState<{ record: Check | null } | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/rtw-checks", { params: { path: { employee_id: id } } }),
      );
      if (!active) return;
      if (result.ok) {
        setData(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [id, refresh]);
  async function download(record: Check, pdf: boolean) {
    setBusy(record.id);
    setProblem(null);
    if (pdf) {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/rtw-checks/{check_id}/evidence.pdf", {
          params: { path: { employee_id: id, check_id: record.id } },
          parseAs: "blob",
        }),
      );
      setBusy(null);
      if (!result.ok) return setProblem(result.problem);
      const url = URL.createObjectURL(result.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "rtw-" + record.id + ".pdf";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } else {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/rtw-checks/{check_id}/evidence", {
          params: { path: { employee_id: id, check_id: record.id } },
        }),
      );
      setBusy(null);
      if (!result.ok) return setProblem(result.problem);
      const link = document.createElement("a");
      link.href = result.data.url;
      link.rel = "noreferrer";
      link.click();
    }
  }
  function details(record: Check) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-headline text-label">
            {CHECK_TYPES.find((t) => t.value === record.check_type)?.label}
          </h3>
          <RTWChip status={record.status} />
          {record.superseded_at && (
            <span className="text-caption text-label-secondary">Superseded</span>
          )}
        </div>
        <dl className="grid gap-3 sm:grid-cols-2">
          {[
            ["Date of check", record.check_date ? shortDate(record.check_date) : "Not set"],
            ["Checked by", record.checker_name ?? "Not set"],
            ["Outcome", record.outcome],
            [
              "Follow-up due",
              record.follow_up_due_on
                ? shortDate(record.follow_up_due_on)
                : "No follow-up required",
            ],
            ["Evidence", record.evidence_file_name ?? "Evidence missing"],
            ...(record.share_code_masked
              ? [["Share code (masked)", record.share_code_masked]]
              : []),
            ...(record.idsp_provider
              ? [
                  ["Certified provider", record.idsp_provider],
                  ["Document", record.idsp_document?.replaceAll("_", " ")],
                ]
              : []),
            ...(record.list_b_group
              ? [
                  [
                    "List B group",
                    record.list_b_group === "group1"
                      ? "Group 1 — document expiry"
                      : "Group 2 — Positive Verification Notice",
                  ],
                ]
              : []),
            ...(record.correction_reason ? [["Correction reason", record.correction_reason]] : []),
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-caption text-label-secondary">{label}</dt>
              <dd className="text-body text-label break-words">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2">
          {record.evidence_file_id && (
            <Button
              variant="gray"
              size="sm"
              loading={busy === record.id}
              onClick={() => void download(record, false)}
            >
              View evidence
            </Button>
          )}
          {can("document.report.generate") && (
            <Button
              variant="gray"
              size="sm"
              loading={busy === record.id}
              onClick={() => void download(record, true)}
            >
              Evidence sheet PDF
            </Button>
          )}
          {can("employee.rtw.correct") && record.can_correct && (
            <Button variant="plain" size="sm" onClick={() => setSheet({ record })}>
              Correct check
            </Button>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap justify-between items-center gap-3">
        <h2 className="text-headline text-label">Right to Work</h2>
        {can("employee.rtw.write") && (
          <Button size="sm" onClick={() => setSheet({ record: null })}>
            Record a check
          </Button>
        )}
      </div>
      {problem && <Alert tone="danger" title={problem.message} />}
      {!data && !problem && (
        <p role="status" className="text-body text-label-secondary">
          Loading Right to Work…
        </p>
      )}
      {data && (
        <section
          aria-label="Current Right to Work check"
          className="bg-elevated rounded-card shadow-e1 p-4"
        >
          {data.current ? (
            details(data.current)
          ) : (
            <Alert tone="warning" title="No Right to Work check recorded">
              Record the check and attach the evidence you kept.
            </Alert>
          )}
        </section>
      )}
      {data && data.checks.some((c) => c.superseded_at) && (
        <section
          aria-label="Right to Work history"
          className="bg-elevated rounded-card shadow-e1 p-4"
        >
          <h2 className="text-headline text-label mb-4">Check history</h2>
          <div className="flex flex-col gap-6">
            {data.checks
              .filter((c) => c.superseded_at)
              .map((record) => (
                <div key={record.id} className="border-separator border-t pt-4">
                  {details(record)}
                </div>
              ))}
          </div>
        </section>
      )}
      {sheet && (
        <CheckSheet
          id={id}
          record={sheet.record}
          onClose={() => setSheet(null)}
          onSaved={() => {
            setRefresh((v) => v + 1);
            onChanged();
          }}
        />
      )}
    </div>
  );
}

function CheckSheet({
  id,
  record,
  onClose,
  onSaved,
}: {
  id: string;
  record: Check | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const me = useMe();
  const toast = useToast();
  const [form, setForm] = useState({
    check_type: record?.check_type ?? ("online_share_code" as Schemas["CheckIn"]["check_type"]),
    share_code: "",
    idsp_provider: record?.idsp_provider ?? "",
    idsp_document: record?.idsp_document ?? "british_passport",
    list_b_group: record?.list_b_group ?? "group1",
    permission_expires: record?.permission_expires ?? false,
    permission_expires_on: record?.permission_expires_on ?? null,
    check_date: record?.check_date ?? today(),
    checked_by_user_id: record?.checked_by_user_id ?? me?.user.id ?? "",
    outcome: record?.outcome ?? ("pending" as Schemas["CheckIn"]["outcome"]),
    evidence_file_id: record?.evidence_file_id ?? "",
    reason: "",
  });
  const [documents, setDocuments] = useState<Schemas["EmployeeDocumentOut"][]>([]);
  const [users, setUsers] = useState<Schemas["AccessUser"][]>([]);
  const [pending, setPending] = useState<File | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string>();
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((c) => ({ ...c, [key]: value }));
  useEffect(() => {
    let active = true;
    async function load() {
      const [docs, people] = await Promise.all([
        attempt((c) =>
          c.GET("/employees/{employee_id}/documents", { params: { path: { employee_id: id } } }),
        ),
        attempt((c) => c.GET("/users")),
      ]);
      if (!active) return;
      if (docs.ok) setDocuments(docs.data);
      else setProblem(docs.problem);
      if (people.ok) setUsers(people.data.users.filter((u) => u.user_id));
      else setProblem(people.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [id]);
  async function upload() {
    if (!pending) return setError("Choose an evidence file first.");
    setUploading(true);
    setProblem(null);
    const body = new FormData();
    body.append("file", pending);
    body.append("category", "rtw_evidence");
    const result = await attempt((c) =>
      c.POST("/employees/{employee_id}/documents", {
        params: { path: { employee_id: id } },
        body: { file: "", category: "rtw_evidence" },
        bodySerializer: () => body,
      }),
    );
    setUploading(false);
    if (result.ok) {
      setDocuments((d) => [result.data, ...d]);
      set("evidence_file_id", result.data.file_id);
      setPending(null);
      setError(undefined);
      toast.show({ title: "Evidence uploaded and selected", tone: "success" });
    } else setProblem(result.problem);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setProblem(null);
    if (!form.check_date || !form.checked_by_user_id)
      return setError("Choose the check date and the person who checked it.");
    if (record && !form.reason.trim()) return setError("Enter a reason for the correction.");
    if (pending)
      return setError("Upload the selected evidence file or remove it before saving the check.");
    const body: Schemas["CheckIn"] = {
      check_type: form.check_type,
      share_code:
        form.check_type === "online_share_code"
          ? form.share_code.toUpperCase().replaceAll(" ", "")
          : null,
      idsp_provider: form.check_type === "idsp_digital" ? form.idsp_provider.trim() : null,
      idsp_document:
        form.check_type === "idsp_digital"
          ? (form.idsp_document as Schemas["CheckIn"]["idsp_document"])
          : null,
      list_b_group:
        form.check_type === "manual_list_b"
          ? (form.list_b_group as Schemas["CheckIn"]["list_b_group"])
          : null,
      permission_expires:
        form.check_type === "manual_list_b" ||
        (form.check_type === "online_share_code" && form.permission_expires),
      permission_expires_on:
        form.check_type === "manual_list_b" ||
        (form.check_type === "online_share_code" && form.permission_expires)
          ? form.permission_expires_on
          : null,
      check_date: form.check_date,
      checked_by_user_id: form.checked_by_user_id,
      outcome: form.outcome,
      evidence_file_id: form.evidence_file_id || null,
    };
    setBusy(true);
    const result = await attempt((c) =>
      record
        ? c.POST("/employees/{employee_id}/rtw-checks/{check_id}/correct", {
            params: { path: { employee_id: id, check_id: record.id } },
            body: { ...body, reason: form.reason.trim() },
          })
        : c.POST("/employees/{employee_id}/rtw-checks", {
            params: { path: { employee_id: id } },
            body,
          }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: record ? "Correction recorded" : "Check recorded", tone: "success" });
      onSaved();
      onClose();
    } else setProblem(result.problem);
  }
  const items: UploadItem[] = pending
    ? [{ id: pending.name, name: pending.name, size: pending.size, status: "safe" }]
    : [];
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={record ? "Correct Right to Work check" : "Record Right to Work check"}
      description={
        record
          ? "The original stays in history. Correcting a historical check does not replace the current check."
          : "Record the check you carried out and the evidence you kept."
      }
      onSubmit={save}
      busy={busy || uploading}
      problem={problem}
    >
      <a
        href="https://www.gov.uk/view-right-to-work"
        target="_blank"
        rel="noreferrer"
        className="text-callout text-tint underline"
      >
        Check on GOV.UK
      </a>
      <Select
        label="Check type"
        name="check_type"
        value={form.check_type}
        onChange={(e) => set("check_type", e.target.value as typeof form.check_type)}
      >
        {CHECK_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </Select>
      {form.check_type === "online_share_code" && (
        <>
          <TextField
            label="Share code"
            name="share_code"
            value={form.share_code}
            onChange={(e) => set("share_code", e.target.value)}
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={11}
            hint={
              record
                ? "Re-enter the 9-character code. Stored codes are never shown in full."
                : "9 letters and numbers."
            }
          />
          <Toggle
            label="Does permission run out?"
            checked={form.permission_expires}
            onCheckedChange={(v) => set("permission_expires", v)}
          />
        </>
      )}
      {form.check_type === "idsp_digital" && (
        <>
          <TextField
            label="Certified IDSP provider"
            name="idsp_provider"
            value={form.idsp_provider}
            onChange={(e) => set("idsp_provider", e.target.value)}
          />
          <Select
            label="Eligible identity document"
            name="idsp_document"
            value={form.idsp_document}
            onChange={(e) => set("idsp_document", e.target.value)}
          >
            <option value="british_passport">Valid British passport</option>
            <option value="irish_passport">Valid Irish passport</option>
            <option value="irish_passport_card">Valid Irish passport card</option>
          </Select>
        </>
      )}
      {form.check_type === "manual_list_b" && (
        <Select
          label="List B group"
          name="list_b_group"
          value={form.list_b_group}
          onChange={(e) => set("list_b_group", e.target.value)}
        >
          <option value="group1">Group 1 — document has an expiry date</option>
          <option value="group2">Group 2 — Positive Verification Notice</option>
        </Select>
      )}
      {(form.check_type === "manual_list_b" ||
        (form.check_type === "online_share_code" && form.permission_expires)) && (
        <DatePicker
          label="Permission expires on"
          name="permission_expires_on"
          value={form.permission_expires_on}
          onChange={(v) => set("permission_expires_on", v)}
        />
      )}
      <DatePicker
        label="Date of check"
        name="check_date"
        value={form.check_date}
        max={today()}
        onChange={(v) => set("check_date", v ?? "")}
      />
      <Select
        label="Checked by"
        name="checked_by_user_id"
        value={form.checked_by_user_id}
        onChange={(e) => set("checked_by_user_id", e.target.value)}
      >
        <option value="">Choose a person</option>
        {users.map((u) => (
          <option key={u.id} value={u.user_id ?? ""}>
            {u.first_name} {u.last_name}
            {u.status === "suspended" ? " (inactive)" : ""}
          </option>
        ))}
      </Select>
      <Select
        label="Outcome"
        name="outcome"
        value={form.outcome}
        onChange={(e) => set("outcome", e.target.value as typeof form.outcome)}
      >
        <option value="pending">Pending</option>
        <option value="verified">Verified</option>
        <option value="failed">Failed</option>
      </Select>
      <Select
        label="Evidence document"
        name="evidence_file_id"
        value={form.evidence_file_id}
        onChange={(e) => set("evidence_file_id", e.target.value)}
      >
        <option value="">Not attached</option>
        {documents
          .filter((d) => d.scan_status === "clean")
          .map((d) => (
            <option key={d.id} value={d.file_id}>
              {d.file_name}
            </option>
          ))}
      </Select>
      {form.outcome === "verified" && !form.evidence_file_id && (
        <Alert tone="warning" title="Evidence is missing">
          A verified outcome without clean evidence is shown as Evidence missing.
        </Alert>
      )}
      <FileDrop
        label="Upload evidence"
        description="Files are scanned when you choose Upload evidence."
        accept={[".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]}
        maxBytes={25 * 1024 * 1024}
        items={items}
        onFiles={(f) => setPending(f[0] ?? null)}
        onRemove={() => setPending(null)}
        disabled={uploading || busy}
      />
      <Button
        variant="gray"
        loading={uploading}
        disabled={!pending || busy}
        onClick={() => void upload()}
      >
        Upload evidence
      </Button>
      {record && (
        <TextArea
          label="Reason for correction"
          name="reason"
          value={form.reason}
          onChange={(e) => set("reason", e.target.value)}
          maxLength={1000}
        />
      )}
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}
