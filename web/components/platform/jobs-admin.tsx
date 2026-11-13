"use client";

import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable, type Column } from "@/components/ui/data-table";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt } from "@/lib/auth/request";
import { PAGE_SIZE } from "@/lib/platform/operations";
import { formatUk } from "@/lib/ui/dates";

// Keep in step with api/app/jobs/rerun.py; the API enforces the allow-list again.
const RERUNNABLE = new Set([
  "rtw_status_daily",
  "bank_holidays_weekly",
  "cloudflare_ranges_weekly",
  "files_orphans_daily",
  "report_jobs_sweep",
]);
type Schemas = components["schemas"];
type Failure = Schemas["JobFailuresOut"]["items"][number];
const pageLink = buttonVariants({ variant: "gray", size: "sm" });
export function JobsAdmin({
  queue,
  failures,
  offset,
}: {
  queue: Schemas["JobQueueOut"] | null;
  failures: Schemas["JobFailuresOut"] | null;
  offset: number;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function rerun(id: string) {
    if (busy || reason.trim().length < 5) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await attempt((c) =>
        c.POST("/platform/jobs/failures/{failure_id}/rerun", {
          params: { path: { failure_id: id } },
          body: { reason: reason.trim() },
        }),
      );
      if (result.ok) setNotice(`${result.data.job} queued for another run.`);
      else if (["UNAUTHENTICATED", "FORBIDDEN"].includes(result.problem.code))
        window.location.replace("/session?next=%2Fjobs");
      else setError(result.problem.message);
    } finally {
      setBusy(false);
    }
  }
  const columns: readonly Column<Failure>[] = [
    { id: "date", header: "Date", cell: (row) => formatUk(row.created_at.slice(0, 10)) },
    {
      id: "job",
      header: "Job",
      primary: true,
      cell: (row) => <span className="break-all">{row.job}</span>,
    },
    {
      id: "detail",
      header: "Failure details",
      cell: (row) => <span className="break-all">{JSON.stringify(row.detail)}</span>,
    },
    {
      id: "action",
      header: "Action",
      cell: (row) =>
        RERUNNABLE.has(row.job) ? (
          <ConfirmDialog
            trigger={
              <Button variant="gray" disabled={busy || reason.trim().length < 5}>
                Run again
              </Button>
            }
            title={`Run ${row.job} again?`}
            description="This queues a new run. The failed run stays in the audit log."
            confirmLabel="Queue run"
            confirmDisabled={busy || reason.trim().length < 5}
            onConfirm={() => rerun(row.id)}
          />
        ) : (
          "Re-run the original action instead."
        ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Jobs"
        description="Queue depth and failed scheduled runs. Only safe, allow-listed jobs can be run again."
      />
      {queue ? (
        <p className="text-title-3 text-label mb-6">Waiting in queue: {queue.waiting}</p>
      ) : (
        <Alert tone="danger" title="Could not load queue">
          Reload to try again.
        </Alert>
      )}
      {error && (
        <Alert tone="danger" title="Could not run job">
          {error}
        </Alert>
      )}
      {notice && (
        <Alert tone="success" title="Job queued">
          {notice}
        </Alert>
      )}
      <h2 className="text-title-3 my-4">Failures</h2>
      {!failures ? (
        <Alert tone="danger" title="Could not load failures">
          Reload to try again.
        </Alert>
      ) : failures.items.length === 0 ? (
        <p className="text-callout text-label-secondary">No failed jobs.</p>
      ) : (
        <>
          <TextField
            label="Reason for running again"
            hint="At least 5 characters; saved in the audit log."
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <DataTable
            className="mt-4"
            caption="Failed jobs"
            columns={columns}
            rows={failures.items}
            getRowId={(row) => row.id}
            pageSize={PAGE_SIZE}
            pager={false}
          />
        </>
      )}
      <nav aria-label="Job pages" className="mt-4 flex gap-3">
        {offset > 0 && (
          <a className={pageLink} href={`/jobs?offset=${Math.max(0, offset - PAGE_SIZE)}`}>
            Previous
          </a>
        )}
        {failures && offset + PAGE_SIZE < failures.total && (
          <a className={pageLink} href={`/jobs?offset=${offset + PAGE_SIZE}`}>
            Next
          </a>
        )}
      </nav>
    </>
  );
}
