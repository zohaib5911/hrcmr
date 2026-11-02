"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useCan } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextArea } from "@/components/ui/text-area";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";
import { shortDate } from "@/lib/employees/profile";

type Document = components["schemas"]["EmployeeDocumentOut"];
type Category = Document["category"];
const CATEGORIES: { value: Category; label: string }[] = [
  { value: "employment_contract", label: "Employment contract" },
  { value: "letter", label: "Letter" },
  { value: "hr_record", label: "HR record" },
  { value: "id_document", label: "Identity document" },
  { value: "rtw_evidence", label: "Right to Work evidence" },
  { value: "certificate", label: "Certificate" },
  { value: "payslip", label: "Payslip" },
  { value: "other", label: "Other" },
];
const SCANS = {
  pending: { label: "Scan pending", tone: "warning" },
  clean: { label: "Scan clean", tone: "success" },
  infected: { label: "Unsafe file", tone: "danger" },
  error: { label: "Scan failed", tone: "warning" },
} as const;

export function DocumentsTab({ id }: { id: string }) {
  const can = useCan();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [view, setView] = useState<"all" | "payslips">("all");
  const [busy, setBusy] = useState(true);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sheet, setSheet] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const mayRead = can("document.file.read", "document.file.read_own");
  const load = useCallback(async () => {
    const result = await attempt((c) =>
      c.GET("/employees/{employee_id}/documents", { params: { path: { employee_id: id } } }),
    );
    setBusy(false);
    if (result.ok) {
      setDocuments(result.data);
      setProblem(null);
    } else setProblem(result.problem);
  }, [id]);
  useEffect(() => {
    let active = true;
    async function initialLoad() {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/documents", { params: { path: { employee_id: id } } }),
      );
      if (!active) return;
      setBusy(false);
      if (result.ok) {
        setDocuments(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    }
    if (mayRead) void initialLoad();
    return () => {
      active = false;
    };
  }, [id, mayRead]);
  async function download(record: Document) {
    setDownloading(record.id);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/employees/{employee_id}/documents/{document_id}/download", {
        params: { path: { employee_id: id, document_id: record.id } },
      }),
    );
    setDownloading(null);
    if (!result.ok) return setProblem(result.problem);
    const link = document.createElement("a");
    link.href = result.data.url;
    link.rel = "noreferrer";
    link.click();
  }
  if (!mayRead)
    return <Alert tone="info" title="Your role does not have access to this person's documents." />;
  const shown = documents.filter((d) => view === "all" || d.category === "payslip");
  return (
    <section aria-label="Employee documents" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl
          label="Documents"
          value={view}
          onValueChange={setView}
          segments={[
            { value: "all", label: "All" },
            { value: "payslips", label: "Payslips" },
          ]}
        />
        {can("document.file.write", "document.file.write_own") && (
          <Button size="sm" onClick={() => setSheet(true)}>
            Upload document
          </Button>
        )}
      </div>
      {problem && <Alert tone="danger" title={problem.message} />}
      {busy ? (
        <p className="text-body text-label-secondary" role="status">
          Loading documents…
        </p>
      ) : shown.length === 0 ? (
        <p className="text-body text-label-secondary">
          {view === "payslips" ? "No payslips yet." : "No documents yet."}
        </p>
      ) : (
        <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
          {shown.map((record) => (
            <li key={record.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
              <div className="min-w-0 flex-1">
                <p className="text-body text-label break-words">{record.file_name}</p>
                <p className="text-caption text-label-secondary">
                  {CATEGORIES.find((c) => c.value === record.category)?.label} ·{" "}
                  {shortDate(record.uploaded_at.slice(0, 10))} · {Math.ceil(record.size / 1024)} KB
                </p>
                {record.notes && (
                  <p className="text-callout text-label-secondary break-words mt-1">
                    {record.notes}
                  </p>
                )}
                <div className="mt-2">
                  <StatusChip tone={SCANS[record.scan_status].tone}>
                    {SCANS[record.scan_status].label}
                  </StatusChip>
                </div>
              </div>
              <Button
                variant="gray"
                size="sm"
                disabled={record.scan_status !== "clean"}
                loading={downloading === record.id}
                onClick={() => void download(record)}
              >
                Download
              </Button>
            </li>
          ))}
        </ul>
      )}
      {sheet && (
        <UploadSheet
          id={id}
          defaultCategory={view === "payslips" ? "payslip" : "other"}
          onClose={() => setSheet(false)}
          onSaved={() => void load()}
        />
      )}
    </section>
  );
}

function UploadSheet({
  id,
  defaultCategory,
  onClose,
  onSaved,
}: {
  id: string;
  defaultCategory: Category;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [category, setCategory] = useState<Category>(defaultCategory);
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState<File | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [fileProblem, setFileProblem] = useState<string>();
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setFileProblem(undefined);
    if (!pending) return setFileProblem("Choose the document to add.");
    const body = new FormData();
    body.append("file", pending);
    body.append("category", category);
    if (notes.trim()) body.append("notes", notes.trim());
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/employees/{employee_id}/documents", {
        params: { path: { employee_id: id } },
        body: { file: "", category },
        bodySerializer: () => body,
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Document uploaded", tone: "success" });
      onSaved();
      onClose();
    } else {
      setProblem(result.problem);
      setFileProblem(result.problem.message);
    }
  }
  const items: UploadItem[] = pending
    ? [
        {
          id: pending.name,
          name: pending.name,
          size: pending.size,
          status: fileProblem ? "rejected" : "safe",
          ...(fileProblem ? { message: fileProblem } : {}),
        },
      ]
    : [];
  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title="Upload document"
      description="The document is checked for viruses when you save."
      onSubmit={save}
      busy={busy}
      problem={problem}
    >
      <Select
        label="Category"
        name="category"
        value={category}
        onChange={(e) => setCategory(e.target.value as Category)}
      >
        {CATEGORIES.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
      </Select>
      <FileDrop
        label="Document"
        description="PDF, Word, Excel, CSV, JPG or PNG up to 25 MB."
        accept={[".pdf", ".doc", ".docx", ".xlsx", ".csv", ".jpg", ".jpeg", ".png"]}
        maxBytes={25 * 1024 * 1024}
        items={items}
        onFiles={(files) => {
          setPending(files[0] ?? null);
          setFileProblem(undefined);
        }}
        onRemove={() => setPending(null)}
        disabled={busy}
      />
      {!pending && fileProblem && <Alert tone="danger" title={fileProblem} />}
      <TextArea
        label="Notes (optional)"
        name="notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        maxLength={1000}
      />
    </FormSheet>
  );
}

export function PrintRecord({ id }: { id: string }) {
  const can = useCan();
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  if (!can("document.report.generate")) return null;
  async function download() {
    setBusy(true);
    const result = await attempt((c) =>
      c.GET("/employees/{employee_id}/record.pdf", {
        params: { path: { employee_id: id } },
        parseAs: "blob",
      }),
    );
    setBusy(false);
    if (!result.ok) return toast.show({ title: result.problem.message, tone: "danger" });
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "employee-" + id + ".pdf";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
  return (
    <Button variant="gray" size="sm" loading={busy} onClick={() => void download()}>
      Print record
    </Button>
  );
}
