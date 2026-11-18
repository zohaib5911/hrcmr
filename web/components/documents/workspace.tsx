"use client";

import { FileText } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan, useMe } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { FileDrop } from "@/components/ui/file-drop";
import { LetterDraftSheet } from "@/components/documents/letter-draft-sheet";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { DatePicker } from "@/components/ui/date-picker";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";
import { formatBytes } from "@/lib/ui/files";
import { cacheKey, cached, remember } from "@/lib/api/cache";

type Document = components["schemas"]["CompanyDocumentOut"];
type Documents = components["schemas"]["CompanyDocuments"];
type Category = Document["category"];
const CATEGORIES: { value: Category; label: string }[] = [
  { value: "policy_handbook", label: "Policy or staff handbook" },
  { value: "health_safety", label: "Health & safety" },
  { value: "companies_house", label: "Companies House record" },
  { value: "hmrc_payroll", label: "HMRC or payroll record" },
  { value: "insurance", label: "Insurance certificate" },
  { value: "premises_lease", label: "Premises or lease" },
  { value: "certificate", label: "Certificate or qualification" },
  { value: "hr_template", label: "HR template or form" },
  { value: "training", label: "Training material" },
  { value: "other", label: "Other" },
];
const REVIEW = {
  no_review_date: { label: "No review date", tone: "neutral" },
  current: { label: "Current", tone: "success" },
  review_due: { label: "Review due", tone: "warning" },
  overdue: { label: "Review overdue", tone: "danger" },
} as const;

export function DocumentsWorkspace() {
  const can = useCan();
  const mayRead = can("document.file.read");
  const mayWrite = can("document.file.write");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [due, setDue] = useState(false);
  const [archived, setArchived] = useState(false);
  const [offset, setOffset] = useState(0);
  const [fetched, setData] = useState<Documents | null>(null);
  const [loaded, setLoaded] = useState("");
  const [version, setVersion] = useState(0);
  const [opened, setOpened] = useState<Document | "new" | null>(null);
  const [drafting, setDrafting] = useState(false);
  const aiAvailable = useMe()?.ai_available ?? false;
  const [problem, setProblem] = useState<Problem | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const key = JSON.stringify([search, category, due, archived, offset, version]);
  // O6.1.6: this view's answer once it is in; until then the last one this tab had for it (no
  // skeleton when coming back), while the fresh one loads in the background.
  const cacheId = cacheKey("/documents", {
    search,
    category: category || undefined,
    review_due: due,
    show_archived: archived,
    offset,
    limit: 50,
  });
  const hit = loaded === key ? undefined : cached<Documents>(cacheId);
  const data = hit ?? fetched;
  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    const query = {
      search,
      category: category || undefined,
      review_due: due,
      show_archived: archived,
      offset,
      limit: 50,
    };
    void attempt((c) => c.GET("/documents", { params: { query } })).then((result) => {
      if (!active) return;
      setLoaded(key);
      if (result.ok) {
        remember(cacheId, result.data);
        setData(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead, search, category, due, archived, offset, version, key, cacheId]);
  async function download(row: Document) {
    setDownloading(row.id);
    const result = await attempt((c) =>
      c.GET("/documents/{document_id}/download", { params: { path: { document_id: row.id } } }),
    );
    setDownloading(null);
    if (!result.ok) return setProblem(result.problem);
    const link = document.createElement("a");
    link.href = result.data.url;
    link.rel = "noreferrer";
    link.click();
  }
  const columns: Column<Document>[] = [
    {
      id: "title",
      header: "Document",
      primary: true,
      sortValue: (r) => r.title,
      cell: (r) => (
        <div className="max-w-72 break-words">
          <p>{r.title}</p>
          <p className="text-footnote text-label-secondary break-all">
            {r.file_name} · {formatBytes(r.size)}
          </p>
        </div>
      ),
    },
    {
      id: "category",
      header: "Category",
      cell: (r) => CATEGORIES.find((c) => c.value === r.category)?.label,
    },
    {
      id: "review",
      header: "Next review",
      cell: (r) => (
        <div className="flex flex-wrap items-center gap-2">
          <span>{r.next_review_date ? formatUk(r.next_review_date) : "—"}</span>
          <StatusChip tone={REVIEW[r.review_status].tone}>
            {REVIEW[r.review_status].label}
          </StatusChip>
        </div>
      ),
    },
    {
      id: "status",
      header: "File status",
      cell: (r) => (
        <div className="flex flex-wrap gap-2">
          {r.archived_at && <StatusChip tone="neutral">Archived</StatusChip>}
          <StatusChip
            tone={
              r.scan_status === "clean"
                ? "success"
                : r.scan_status === "infected"
                  ? "danger"
                  : "warning"
            }
          >
            {r.scan_status === "clean"
              ? "Scan clean"
              : r.scan_status === "pending"
                ? "Scan pending"
                : r.scan_status === "infected"
                  ? "Unsafe file"
                  : "Scan failed"}
          </StatusChip>
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (r) => (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="gray"
            size="sm"
            aria-label={`Download ${r.title}`}
            disabled={r.scan_status !== "clean"}
            loading={downloading === r.id}
            onClick={() => void download(r)}
          >
            Download
          </Button>
          {mayWrite && !r.archived_at && (
            <Button
              variant="gray"
              size="sm"
              aria-label={`Edit ${r.title}`}
              onClick={() => setOpened(r)}
            >
              Edit
            </Button>
          )}
        </div>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Documents"
        description="Company files, with their review dates."
        actions={
          mayWrite ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="gray" onClick={() => setDrafting(true)}>
                {aiAvailable ? "Draft with AI" : "Start from template"}
              </Button>
              <Button onClick={() => setOpened("new")}>Upload document</Button>
            </div>
          ) : undefined
        }
      />
      {!mayRead ? (
        <Alert title="Your role does not have access to company documents." />
      ) : (
        <section aria-label="Company documents" className="flex min-w-0 flex-col gap-5">
          <p className="text-callout text-label-secondary">
            Upload per-person files from the{" "}
            <Link href="/employees" className="text-accent-text underline">
              person’s profile
            </Link>
            . Company document reviews are flagged when due within 30 days.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <TextField
              label="Search documents"
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
            <Select
              label="Document category"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value as Category | "");
                setOffset(0);
              }}
            >
              <option value="">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
            <Checkbox
              label="Review due within 30 days"
              checked={due}
              onCheckedChange={(v) => {
                setDue(v === true);
                setOffset(0);
              }}
            />
            <Checkbox
              label="Show archived"
              checked={archived}
              onCheckedChange={(v) => {
                setArchived(v === true);
                setOffset(0);
              }}
            />
          </div>
          {problem && <Alert tone="danger" title={problem.message} />}
          <DataTable
            caption="Company documents"
            columns={columns}
            rows={data?.items ?? []}
            getRowId={(r) => r.id}
            loading={loaded !== key && !hit && !problem}
            pageSize={50}
            empty={
              <EmptyState
                icon={FileText}
                title={search || category || due ? "No matching documents" : "No documents yet"}
                description={
                  search || category || due
                    ? "Try another search or category, or clear the review filter."
                    : "Add company files such as handbooks, insurance certificates and HR templates."
                }
              />
            }
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="gray"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous documents
            </Button>
            <span className="text-footnote text-label-secondary">
              {data?.total ?? 0} documents in this view
            </span>
            <Button
              variant="gray"
              disabled={!data || offset + data.items.length >= data.total}
              onClick={() => setOffset(offset + 50)}
            >
              Next documents
            </Button>
          </div>
        </section>
      )}
      {opened && (
        <DocumentForm
          item={opened === "new" ? null : opened}
          close={() => setOpened(null)}
          saved={() => {
            setOpened(null);
            setVersion((v) => v + 1);
          }}
        />
      )}
      {drafting && (
        <LetterDraftSheet
          aiAvailable={aiAvailable}
          onOpenChange={(open) => {
            if (!open) setDrafting(false);
          }}
          onSaved={() => {
            setDrafting(false);
            setVersion((v) => v + 1);
          }}
        />
      )}
    </>
  );
}

function DocumentForm({
  item,
  close,
  saved,
}: {
  item: Document | null;
  close: () => void;
  saved: () => void;
}) {
  const toast = useToast();
  const [title, setTitle] = useState(item?.title ?? "");
  const [category, setCategory] = useState<Category>(item?.category ?? "policy_handbook");
  const [review, setReview] = useState(item?.next_review_date ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setFileError(null);
    if (!title.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter a document title.",
        field: "title",
      });
    if (!item && !file) return setFileError("Choose the document to upload.");
    setBusy(true);
    const metadata = { title: title.trim(), category, next_review_date: review || null };
    const body = new FormData();
    body.append("title", metadata.title);
    body.append("category", category);
    if (review) body.append("next_review_date", review);
    if (file) body.append("file", file);
    const result = await (item
      ? attempt((c) =>
          c.PATCH("/documents/{document_id}", {
            params: { path: { document_id: item.id } },
            body: metadata,
          }),
        )
      : attempt((c) =>
          c.POST("/documents", {
            body: { file: "", title: metadata.title, category },
            bodySerializer: () => body,
          }),
        ));
    setBusy(false);
    if (result.ok) {
      toast.show({ title: item ? "Document updated" : "Document uploaded", tone: "success" });
      saved();
    } else setProblem(result.problem);
  }
  async function archive() {
    if (!item) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.DELETE("/documents/{document_id}", { params: { path: { document_id: item.id } } }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Document archived", tone: "success" });
      saved();
    } else setProblem(result.problem);
  }
  return (
    <FormSheet
      open
      title={item ? "Edit document" : "Upload document"}
      description={
        item
          ? "Update the title, category or next review date."
          : "Choose a company file. It is checked for viruses before anyone can download it."
      }
      onOpenChange={(v) => {
        if (!v) close();
      }}
      onSubmit={(e) => void submit(e)}
      busy={busy}
      problem={problem}
      saveLabel={item ? "Save changes" : "Upload document"}
      archive={
        item
          ? {
              label: "Archive",
              question: "Archive this document?",
              detail: "The document stays in the archive with its file and history.",
              onConfirm: archive,
            }
          : undefined
      }
    >
      <fieldset disabled={busy} className="flex min-w-0 flex-col gap-4">
        <TextField
          label="Title"
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={problem?.field === "title" ? problem.message : undefined}
        />
        <Select
          label="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value as Category)}
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </Select>
        <DatePicker
          label="Next review date (optional)"
          value={review || null}
          onChange={(picked) => setReview(picked ?? "")}
          hint="Flagged when overdue or due within 30 days."
        />
        {item ? (
          <p className="text-callout text-label-secondary break-all">
            {item.file_name} · {formatBytes(item.size)}
          </p>
        ) : (
          <>
            <FileDrop
              label="Company document file"
              description="PDF, JPG, PNG or Word, up to 25 MB."
              accept={[".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]}
              maxBytes={25 * 1024 * 1024}
              items={
                file && busy
                  ? [{ id: file.name, name: file.name, size: file.size, status: "uploading" }]
                  : []
              }
              onFiles={(files) => {
                setFile(files[0] ?? null);
                setFileError(null);
              }}
              disabled={busy}
            />
            {file && !busy && (
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-callout text-label break-all">Selected: {file.name}</p>
                <Button variant="plain" size="sm" onClick={() => setFile(null)}>
                  Remove selected file
                </Button>
              </div>
            )}
            {fileError && <Alert tone="danger" title={fileError} />}
          </>
        )}
      </fieldset>
    </FormSheet>
  );
}
