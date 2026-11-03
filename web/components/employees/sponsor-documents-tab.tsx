"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useCan } from "@/components/app/session-context";
import { EmployeeChanges } from "@/components/compliance/change-log";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { NumberField } from "@/components/ui/number-field";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import {
  DOCUMENT_TYPES,
  VISA_ROUTES,
  DOCUMENT_STATUS,
  documentLabel,
  routeLabel,
  type DocumentType,
  type SponsorDocument,
} from "@/lib/compliance/sponsor-documents";
import { shortDate } from "@/lib/employees/profile";

type Schemas = components["schemas"];
type Sheet =
  | { kind: "record"; type: DocumentType; record: SponsorDocument | null }
  | { kind: "withdraw" | "renewal"; record: SponsorDocument };
const today = () => new Date().toISOString().slice(0, 10);

export function SponsorDocumentsTab({ id, onChanged }: { id: string; onChanged: () => void }) {
  const can = useCan();
  const [records, setRecords] = useState<SponsorDocument[] | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const mayWrite = can("employee.rtw.write");
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/sponsor-documents", {
          params: { path: { employee_id: id } },
        }),
      );
      if (!active) return;
      if (result.ok) {
        setRecords(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [id, refresh]);
  async function evidence(record: SponsorDocument) {
    setDownloading(record.id);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/sponsor-documents/{document_id}/evidence", {
        params: { path: { document_id: record.id } },
      }),
    );
    setDownloading(null);
    if (!result.ok) return setProblem(result.problem);
    const link = document.createElement("a");
    link.href = result.data.url;
    link.rel = "noreferrer";
    link.click();
  }
  async function printRecord() {
    setDownloading("record");
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/employees/{employee_id}/sponsor-record.pdf", {
        params: { path: { employee_id: id } },
        parseAs: "blob",
      }),
    );
    setDownloading(null);
    if (!result.ok) return setProblem(result.problem);
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sponsor-record-" + id + ".pdf";
    link.click();
    URL.revokeObjectURL(url);
  }
  const saved = () => {
    setRefresh((v) => v + 1);
    onChanged();
  };
  function details(record: SponsorDocument) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-callout text-label">Version {record.version}</span>
          <StatusChip tone={DOCUMENT_STATUS[record.status].tone}>
            {DOCUMENT_STATUS[record.status].label}
          </StatusChip>
        </div>
        <dl className="grid gap-3 sm:grid-cols-2">
          {[
            ["Reference (masked)", record.reference_number_masked ?? "Not set"],
            ["Issuing country", record.issuing_country ?? "Not set"],
            ...(record.doc_type === "visa"
              ? [
                  ["Visa route", routeLabel(record.visa_route)],
                  ["CoS number (masked)", record.cos_number_masked ?? "Not set"],
                  ["SOC code", record.soc_code ?? "Not set"],
                  ...(can("employee.compensation.read")
                    ? [
                        [
                          "Sponsored annual salary",
                          record.sponsored_salary
                            ? "£" +
                              Number(record.sponsored_salary).toLocaleString("en-GB", {
                                minimumFractionDigits: 2,
                              })
                            : "Not set",
                        ],
                      ]
                    : []),
                ]
              : []),
            ["Issue date", record.issue_date ? shortDate(record.issue_date) : "Not set"],
            ["Expiry date", record.expiry_date ? shortDate(record.expiry_date) : "Not set"],
            ["Review date", record.review_date ? shortDate(record.review_date) : "Not set"],
            ["Evidence", record.evidence_file_name ?? "Not attached"],
            ...(record.renewal_date
              ? [
                  ["Renewal target", shortDate(record.renewal_date)],
                  ["Renewal notes", record.renewal_notes ?? "Not set"],
                ]
              : []),
            ...(record.remarks ? [["Remarks", record.remarks]] : []),
            ...(record.withdraw_reason ? [["Withdrawal reason", record.withdraw_reason]] : []),
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-caption text-label-secondary">{label}</dt>
              <dd className="text-body text-label break-words">{value}</dd>
            </div>
          ))}
        </dl>
        {record.evidence_file_id && (
          <div>
            <Button
              variant="gray"
              size="sm"
              disabled={record.evidence_scan_status !== "clean"}
              loading={downloading === record.id}
              onClick={() => void evidence(record)}
            >
              View evidence
            </Button>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-headline text-label">Sponsor documents</h2>
        {can("document.report.generate") && (
          <Button
            variant="gray"
            loading={downloading === "record"}
            onClick={() => void printRecord()}
          >
            Sponsor compliance record PDF
          </Button>
        )}
      </div>
      {problem && <Alert tone="danger" title={problem.message} />}
      {!records && !problem && (
        <p role="status" className="text-body text-label-secondary">
          Loading sponsor documents…
        </p>
      )}
      {records &&
        DOCUMENT_TYPES.map((type) => {
          const current = records.find(
            (r) => r.doc_type === type.value && !r.superseded_by && !r.withdrawn_at,
          );
          const history = records.filter(
            (r) => r.doc_type === type.value && (r.superseded_by || r.withdrawn_at),
          );
          return (
            <section
              key={type.value}
              aria-label={type.label + " document"}
              className="bg-elevated rounded-card shadow-e1 p-4 flex flex-col gap-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-headline text-label">{type.label}</h3>
                {mayWrite && (
                  <Button
                    size="sm"
                    variant="gray"
                    onClick={() =>
                      setSheet({ kind: "record", type: type.value, record: current ?? null })
                    }
                  >
                    {current ? "Update " + type.label : "Add " + type.label}
                  </Button>
                )}
              </div>
              {current ? (
                <>
                  {details(current)}
                  {mayWrite && (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="plain"
                        size="sm"
                        onClick={() => setSheet({ kind: "renewal", record: current })}
                      >
                        Plan renewal
                      </Button>
                      <Button
                        variant="plain"
                        size="sm"
                        onClick={() => setSheet({ kind: "withdraw", record: current })}
                      >
                        Withdraw
                      </Button>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-body text-label-secondary">
                  No current {type.label.toLowerCase()} recorded.
                </p>
              )}
              {history.length > 0 && (
                <details className="border-separator border-t pt-3">
                  <summary className="text-callout text-label cursor-pointer">
                    {type.label} history ({history.length})
                  </summary>
                  <div className="mt-4 flex flex-col gap-6">
                    {history.map((record) => (
                      <div key={record.id}>{details(record)}</div>
                    ))}
                  </div>
                </details>
              )}
            </section>
          );
        })}
      {can("employee.change_of_circumstances.read") && <EmployeeChanges id={id} />}
      {sheet &&
        (sheet.kind === "record" ? (
          <DocumentSheet
            id={id}
            type={sheet.type}
            record={sheet.record}
            onClose={() => setSheet(null)}
            onSaved={saved}
          />
        ) : (
          <LifecycleSheet
            kind={sheet.kind}
            record={sheet.record}
            onClose={() => setSheet(null)}
            onSaved={saved}
          />
        ))}
    </div>
  );
}

function DocumentSheet({
  id,
  type,
  record,
  onClose,
  onSaved,
}: {
  id: string;
  type: DocumentType;
  record: SponsorDocument | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState({
    reference_number: "",
    issuing_country: record?.issuing_country ?? "",
    visa_route: record?.visa_route ?? "skilled_worker",
    cos_number: "",
    soc_code: record?.soc_code ?? "",
    sponsored_salary: record?.sponsored_salary ? Number(record.sponsored_salary) : null,
    issue_date: record?.issue_date ?? null,
    expiry_date: record?.expiry_date ?? null,
    review_date: record?.review_date ?? null,
    evidence_file_id: record?.evidence_file_id ?? "",
    remarks: record?.remarks ?? "",
  });
  const [documents, setDocuments] = useState<Schemas["EmployeeDocumentOut"][]>([]);
  const [pending, setPending] = useState<File | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((c) => ({ ...c, [key]: value }));
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/documents", { params: { path: { employee_id: id } } }),
      );
      if (!active) return;
      if (result.ok) setDocuments(result.data);
      else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [id]);
  async function upload() {
    if (!pending) return;
    setUploading(true);
    setProblem(null);
    const body = new FormData();
    body.append("file", pending);
    body.append("category", "id_document");
    const result = await attempt((c) =>
      c.POST("/employees/{employee_id}/documents", {
        params: { path: { employee_id: id } },
        body: { file: "", category: "id_document" },
        bodySerializer: () => body,
      }),
    );
    setUploading(false);
    if (!result.ok) return setProblem(result.problem);
    setDocuments((d) => [result.data, ...d]);
    set("evidence_file_id", result.data.file_id);
    setPending(null);
    setError(undefined);
    toast.show({ title: "Evidence uploaded and selected", tone: "success" });
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setError(undefined);
    if (pending)
      return setError("Upload the selected evidence file or remove it before saving the document.");
    const body: Schemas["SponsorDocumentIn"] = {
      doc_type: type,
      reference_number: form.reference_number.trim() || null,
      issuing_country: form.issuing_country.trim().toUpperCase() || null,
      visa_route: type === "visa" ? form.visa_route : null,
      cos_number: type === "visa" ? form.cos_number.trim() || null : null,
      soc_code: type === "visa" ? form.soc_code.trim() || null : null,
      sponsored_salary:
        type === "visa" && form.sponsored_salary !== null ? String(form.sponsored_salary) : null,
      issue_date: form.issue_date,
      expiry_date: form.expiry_date,
      review_date: form.review_date,
      evidence_file_id: form.evidence_file_id || null,
      remarks: form.remarks.trim() || null,
    };
    setBusy(true);
    const result = await attempt((c) =>
      record
        ? c.POST("/sponsor-documents/{document_id}/versions", {
            params: { path: { document_id: record.id } },
            body,
          })
        : c.POST("/employees/{employee_id}/sponsor-documents", {
            params: { path: { employee_id: id } },
            body,
          }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({
        title: record ? "New document version recorded" : "Sponsor document added",
        tone: "success",
      });
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
      title={(record ? "Update " : "Add ") + documentLabel(type)}
      description={
        record
          ? "Save a new version. The original stays in history. Leave references blank to keep the stored values."
          : "Record the document and attach the evidence you kept."
      }
      busy={busy || uploading}
      problem={problem}
      onSubmit={save}
    >
      <TextField
        label={type === "visa" ? "eVisa or visa reference" : "Document reference"}
        name="reference_number"
        value={form.reference_number}
        onChange={(e) => set("reference_number", e.target.value)}
        maxLength={160}
        autoComplete="off"
        hint={
          record
            ? "Leave blank to keep " + (record.reference_number_masked ?? "the current value")
            : undefined
        }
      />
      <TextField
        label="Issuing country"
        name="issuing_country"
        value={form.issuing_country}
        onChange={(e) => set("issuing_country", e.target.value)}
        maxLength={2}
        autoCapitalize="characters"
        hint="Two-letter country code, such as GB."
      />
      {type === "visa" && (
        <>
          <Select
            label="Visa route"
            name="visa_route"
            value={form.visa_route}
            onChange={(e) => set("visa_route", e.target.value as typeof form.visa_route)}
          >
            {VISA_ROUTES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
          <TextField
            label="CoS number"
            name="cos_number"
            value={form.cos_number}
            onChange={(e) => set("cos_number", e.target.value)}
            autoComplete="off"
            maxLength={160}
            hint={
              record
                ? "Leave blank to keep " + (record.cos_number_masked ?? "the current value")
                : undefined
            }
          />
          <TextField
            label="SOC code"
            name="soc_code"
            value={form.soc_code}
            onChange={(e) => set("soc_code", e.target.value)}
            maxLength={4}
            inputMode="numeric"
            hint="4 digits."
          />
          <Link
            href="/sponsorship-checker"
            target="_blank"
            rel="noreferrer"
            className="text-callout text-tint underline"
          >
            Find code
          </Link>
          <NumberField
            label="Sponsored annual salary"
            name="sponsored_salary"
            unit="currency"
            min={0}
            value={form.sponsored_salary}
            onChange={(v) => set("sponsored_salary", v)}
          />
        </>
      )}
      <DatePicker
        label="Issue date"
        name="issue_date"
        value={form.issue_date}
        onChange={(v) => set("issue_date", v)}
      />
      <DatePicker
        label="Expiry date"
        name="expiry_date"
        value={form.expiry_date}
        onChange={(v) => set("expiry_date", v)}
      />
      <DatePicker
        label="Review date"
        name="review_date"
        value={form.review_date}
        onChange={(v) => set("review_date", v)}
      />
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
      <FileDrop
        label="Upload evidence"
        description="Files are scanned when you choose Upload evidence."
        accept={[".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]}
        maxBytes={25 * 1024 * 1024}
        items={items}
        onFiles={(f) => setPending(f[0] ?? null)}
        onRemove={() => setPending(null)}
        disabled={busy || uploading}
      />
      <Button
        variant="gray"
        onClick={() => void upload()}
        loading={uploading}
        disabled={!pending || busy}
      >
        Upload evidence
      </Button>
      <TextArea
        label="Remarks"
        name="remarks"
        value={form.remarks}
        onChange={(e) => set("remarks", e.target.value)}
        maxLength={2000}
      />
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}

function LifecycleSheet({
  kind,
  record,
  onClose,
  onSaved,
}: {
  kind: "withdraw" | "renewal";
  record: SponsorDocument;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [date, setDate] = useState<string | null>(record.renewal_date ?? today());
  const [notes, setNotes] = useState(record.renewal_notes ?? "");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setProblem(null);
    if (kind === "withdraw" && !reason.trim()) return setError("Enter a reason for withdrawal.");
    if (kind === "renewal" && !date) return setError("Choose the renewal target date.");
    setBusy(true);
    const result = await attempt((c) =>
      kind === "withdraw"
        ? c.POST("/sponsor-documents/{document_id}/withdraw", {
            params: { path: { document_id: record.id } },
            body: { reason: reason.trim() },
          })
        : c.POST("/sponsor-documents/{document_id}/renewal", {
            params: { path: { document_id: record.id } },
            body: { renewal_date: date!, notes: notes.trim() || null },
          }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({
        title: kind === "withdraw" ? "Document withdrawn" : "Renewal planned",
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
      title={
        (kind === "withdraw" ? "Withdraw " : "Plan renewal for ") + documentLabel(record.doc_type)
      }
      description={
        kind === "withdraw"
          ? "This version stays in history with your reason. It will no longer be current."
          : "Set a target date and next steps. The document's expiry stays the same."
      }
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      {kind === "withdraw" ? (
        <TextArea
          label="Reason for withdrawal"
          name="reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={1000}
        />
      ) : (
        <>
          <DatePicker
            label="Renewal target date"
            name="renewal_date"
            value={date}
            min={today()}
            onChange={setDate}
          />
          <TextArea
            label="Renewal notes"
            name="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={2000}
          />
        </>
      )}
      {error && <Alert tone="danger" title={error} />}
    </FormSheet>
  );
}
