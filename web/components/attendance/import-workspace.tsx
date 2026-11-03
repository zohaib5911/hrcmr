"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { FileDrop } from "@/components/ui/file-drop";
import { InlineConfirm } from "@/components/ui/inline-confirm";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import type { components } from "@/lib/api/client";
import { downloadBlob } from "@/lib/attendance";
import { attempt, type Problem } from "@/lib/auth/request";

type Preview = components["schemas"]["AttendanceImportOut"];
type Row = components["schemas"]["ImportRowOut"];

export function AttendanceImport({ previewId }: { previewId?: string }) {
  const can = useCan();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [opened, setOpened] = useState<Row | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    if (!previewId) return;
    let active = true;
    const current = generation.current;
    void attempt((c) =>
      c.GET("/attendance/import/{import_id}", { params: { path: { import_id: previewId } } }),
    ).then((result) => {
      if (!active || current !== generation.current) return;
      if (result.ok) setPreview(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [previewId]);
  async function template(kind: "xlsx" | "csv") {
    const result = await attempt((c) =>
      kind === "xlsx"
        ? c.GET("/attendance/import/template.xlsx", { parseAs: "blob" })
        : c.GET("/attendance/import/template.csv", { parseAs: "blob" }),
    );
    if (result.ok) downloadBlob(result.data, `attendance-template.${kind}`);
    else setProblem(result.problem);
  }
  async function upload() {
    if (!file) return;
    const current = ++generation.current;
    setBusy(true);
    setProblem(null);
    setPreview(null);
    const form = new FormData();
    form.append("file", file);
    const result = await attempt((c) =>
      c.POST("/attendance/import/preview", {
        body: { file: "" },
        bodySerializer: () => form,
      }),
    );
    if (current !== generation.current) return;
    setBusy(false);
    if (result.ok) {
      setPreview(result.data);
      router.replace(`/attendance/import?preview=${result.data.id}`);
    } else setProblem(result.problem);
  }
  async function commit() {
    if (!preview) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/attendance/import/{import_id}/commit", {
        params: { path: { import_id: preview.id } },
      }),
    );
    setBusy(false);
    if (result.ok) setPreview(result.data);
    else setProblem(result.problem);
  }
  const columns: Column<Row>[] = [
    { id: "row", header: "Row", cell: (r) => r.number },
    {
      id: "employee",
      header: "Employee",
      primary: true,
      cell: (r) => (
        <span>
          {r.employee_name ?? r.values.employee_number ?? "Unknown"}
          <span className="text-caption text-label-secondary block">
            {r.values.employee_number}
          </span>
        </span>
      ),
    },
    { id: "date", header: "Date", cell: (r) => r.values.date },
    { id: "status", header: "Status", cell: (r) => r.values.status },
    {
      id: "times",
      header: "Times",
      cell: (r) => `${r.values.clock_in || "—"} to ${r.values.clock_out || "—"}`,
    },
    {
      id: "action",
      header: "Result",
      cell: (r) =>
        r.errors.length ? (
          <span className="text-danger">{r.errors.join(" ")}</span>
        ) : r.action === "update" ? (
          "Update existing"
        ) : (
          "Create"
        ),
    },
    {
      id: "view",
      header: "Details",
      cell: (r) => (
        <Button size="sm" variant="gray" onClick={() => setOpened(r)}>
          View row {r.number}
        </Button>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Import attendance"
        description="Upload a spreadsheet, review every row, then save the records."
        actions={
          <Button asChild variant="gray">
            <Link href="/attendance">Attendance</Link>
          </Button>
        }
      />
      {!can("attendance.record.write") ? (
        <Alert title="Attendance imports need company-wide write access." />
      ) : (
        <div className="flex flex-col gap-5">
          {problem && <Alert tone="danger" title={problem.message} />}
          <div className="flex flex-wrap gap-2">
            <Button variant="gray" onClick={() => void template("xlsx")}>
              Download Excel template
            </Button>
            <Button variant="gray" onClick={() => void template("csv")}>
              Download CSV template
            </Button>
          </div>
          <p className="text-callout text-label-secondary">
            Match employees by employee number. Use YYYY-MM-DD dates and 24-hour times. Up to 1,000
            rows; all row errors must be fixed before saving.
          </p>
          <FileDrop
            label="Attendance spreadsheet"
            description="CSV or XLSX, up to 5 MB. Files are scanned before preview."
            accept={[".csv", ".xlsx"]}
            maxBytes={5 * 1024 * 1024}
            disabled={busy}
            items={
              file && (busy || preview)
                ? [
                    {
                      id: "file",
                      name: file.name,
                      size: file.size,
                      status: busy ? "scanning" : "safe",
                    },
                  ]
                : []
            }
            onFiles={(files) => {
              generation.current++;
              setFile(files[0] ?? null);
              setPreview(null);
              setProblem(null);
              router.replace("/attendance/import");
            }}
          />
          {file && <p className="text-callout text-label">Selected file: {file.name}</p>}
          <div>
            <Button loading={busy} disabled={!file} onClick={() => void upload()}>
              Preview import
            </Button>
          </div>
          {preview && (
            <section aria-label="Import preview" className="flex flex-col gap-4">
              <h2 className="text-title-3 text-label">{preview.filename}</h2>
              <p>
                {preview.rows_valid} of {preview.rows_total} rows valid ·{" "}
                {preview.from_date ?? "No valid date"} to {preview.to_date ?? "—"}
              </p>
              {preview.status === "committed" ? (
                <Alert tone="success" title="Attendance imported">
                  <Link
                    className="text-accent-text underline"
                    href={`/attendance?month=${preview.from_date?.slice(0, 7) ?? ""}`}
                  >
                    View imported attendance
                  </Link>
                </Alert>
              ) : (
                <>
                  {preview.rows_valid !== preview.rows_total && (
                    <Alert
                      tone="warning"
                      title="Fix the row errors in your file, then upload it again. No attendance has been saved."
                    />
                  )}
                  <InlineConfirm
                    label="Commit import"
                    prompt={`Save all ${preview.rows_total} attendance records?`}
                    confirmLabel="Save records"
                    disabled={
                      busy || preview.rows_total === 0 || preview.rows_valid !== preview.rows_total
                    }
                    onConfirm={commit}
                  />
                </>
              )}
              <DataTable
                caption="Attendance import rows"
                rows={preview.rows}
                columns={columns}
                getRowId={(r) => String(r.number)}
                onRowOpen={setOpened}
              />
            </section>
          )}
        </div>
      )}
      <Sheet
        open={opened !== null}
        onOpenChange={(open) => {
          if (!open) setOpened(null);
        }}
      >
        {opened && (
          <SheetContent title={`Import row ${opened.number}`} readOnly>
            <dl className="flex flex-col gap-3">
              {Object.entries(opened.values).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-caption text-label-secondary">{key.replaceAll("_", " ")}</dt>
                  <dd className="whitespace-pre-wrap break-words">{value || "—"}</dd>
                </div>
              ))}
            </dl>
            {opened.errors.map((error) => (
              <Alert key={error} tone="danger" title={error} />
            ))}
          </SheetContent>
        )}
      </Sheet>
    </>
  );
}
