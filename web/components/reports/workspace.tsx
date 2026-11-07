"use client";

import { FileSpreadsheet } from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Job = components["schemas"]["ReportJobOut"];
type Kind = Job["report_type"];
const REPORTS: { kind: Kind; title: string; description: string }[] = [
  {
    kind: "employee_directory",
    title: "Employee Directory",
    description: "Employee numbers, names, departments, status and hire dates.",
  },
  {
    kind: "employee_detail",
    title: "Employee Detail",
    description:
      "Directory details plus designation, location, leaving date and Right to Work status.",
  },
  {
    kind: "archived_employees",
    title: "Archived Employees",
    description: "Archived employee records, with department and hire date.",
  },
  {
    kind: "company",
    title: "Company Report",
    description:
      "Company details, addresses, HR settings, departments, key personnel, trading hours and compliance documents.",
  },
  {
    kind: "sponsor_workers",
    title: "Sponsor Workers Report",
    description: "Sponsored employees, visa routes, SOC codes and review dates.",
  },
  {
    kind: "leave_taken",
    title: "Leave Taken Report",
    description: "Approved leave taken through today, using each person’s working pattern.",
  },
  {
    kind: "training_completion",
    title: "Training Completion Report",
    description: "Completed training recorded on employee profiles.",
  },
];
const STATUS = {
  queued: { label: "Preparing", tone: "warning" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Could not generate", tone: "danger" },
} as const;
const ERRORS: Record<string, string> = {
  ACCESS_REVOKED: "Your report access changed before this report was generated.",
  STORAGE_NOT_CONFIGURED: "Report file storage is not set up on this server.",
  REPORT_TOO_LARGE: "This report exceeds the supported size.",
  REPORT_FAILED: "We could not generate this report. Try generating a new one.",
};
const titleFor = (kind: Kind) => REPORTS.find((r) => r.kind === kind)?.title ?? kind;

export function ReportsWorkspace() {
  const can = useCan();
  const mayGenerate = can("document.report.generate");
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [version, setVersion] = useState(0);
  const [requesting, setRequesting] = useState<Kind | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  useEffect(() => {
    if (!mayGenerate) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      const result = await attempt((c) => c.GET("/reports/jobs"));
      if (!active) return;
      setLoaded(true);
      if (result.ok) {
        setJobs(result.data);
        if (result.data.some((job) => job.status === "queued"))
          timer = setTimeout(() => void refresh(), 1500);
      } else setProblem(result.problem);
    }
    void refresh();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [mayGenerate, version]);
  async function generate(kind: Kind) {
    setRequesting(kind);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/reports/{report_type}", { params: { path: { report_type: kind } } }),
    );
    setRequesting(null);
    if (!result.ok) return setProblem(result.problem);
    toast.show({ title: "Report requested", tone: "success" });
    setVersion((v) => v + 1);
  }
  async function download(job: Job) {
    setDownloading(job.id);
    setProblem(null);
    // Issue a new short-lived link on every click, including after the page has stayed open.
    const result = await attempt((c) =>
      c.GET("/reports/jobs/{job_id}", { params: { path: { job_id: job.id } } }),
    );
    setDownloading(null);
    if (!result.ok) return setProblem(result.problem);
    if (!result.data.url) return;
    const link = document.createElement("a");
    link.href = result.data.url;
    link.rel = "noreferrer";
    link.click();
  }
  const columns: Column<Job>[] = [
    {
      id: "report",
      header: "Report",
      primary: true,
      sortValue: (j) => titleFor(j.report_type),
      cell: (j) => <span className="break-words">{titleFor(j.report_type)}</span>,
    },
    {
      id: "requested",
      header: "Requested",
      cell: (j) => `${j.created_at.replace("T", " ").slice(0, 16)} UTC`,
    },
    {
      id: "status",
      header: "Status",
      cell: (j) => <StatusChip tone={STATUS[j.status].tone}>{STATUS[j.status].label}</StatusChip>,
    },
    {
      id: "file",
      header: "File",
      cell: (j) =>
        j.status === "ready" ? (
          <Button
            variant="gray"
            size="sm"
            aria-label={`Download XLSX: ${titleFor(j.report_type)} requested ${j.created_at}`}
            loading={downloading === j.id}
            onClick={() => void download(j)}
          >
            Download XLSX
          </Button>
        ) : (
          <span className="text-footnote text-label-secondary whitespace-normal">
            {j.status === "failed"
              ? (ERRORS[j.error_code ?? ""] ?? ERRORS.REPORT_FAILED)
              : "Preparing your file…"}
          </span>
        ),
    },
  ];
  return (
    <>
      <PageHeader title="Reports" description="Fresh Excel reports for your company." />
      {!mayGenerate ? (
        <Alert title="Your role does not have access to company reports." />
      ) : (
        <div className="flex min-w-0 flex-col gap-6">
          {problem && <Alert tone="danger" title={problem.message} />}
          <p className="text-callout text-label-secondary">
            Choose a report to generate a fresh XLSX file. The finished file appears below when it
            is ready.
          </p>
          <ul aria-label="Available reports" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {REPORTS.map((report) => (
              <li
                key={report.kind}
                className="bg-elevated rounded-card shadow-e1 flex min-w-0 flex-col items-start gap-3 p-4"
              >
                <h2 className="text-headline text-label">{report.title}</h2>
                <p className="text-callout text-label-secondary flex-1">{report.description}</p>
                <Button
                  variant="gray"
                  aria-label={`Generate report: ${report.title}`}
                  disabled={requesting !== null}
                  loading={requesting === report.kind}
                  onClick={() => void generate(report.kind)}
                >
                  Generate report
                </Button>
              </li>
            ))}
          </ul>
          <section aria-label="Your report files" className="flex min-w-0 flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-title-3 text-label">Your recent reports</h2>
              <Button variant="gray" onClick={() => setVersion((v) => v + 1)}>
                Refresh reports
              </Button>
            </div>
            <p className="text-footnote text-label-secondary">
              Your 20 most recent requests. Each download gets a new link that is valid for 60
              seconds.
            </p>
            <DataTable
              caption="Your report files"
              columns={columns}
              rows={jobs}
              getRowId={(j) => j.id}
              loading={!loaded && !problem}
              pageSize={20}
              empty={
                <EmptyState
                  icon={FileSpreadsheet}
                  title="No reports requested"
                  description="Choose a report above to prepare your first file."
                />
              }
            />
          </section>
        </div>
      )}
    </>
  );
}
