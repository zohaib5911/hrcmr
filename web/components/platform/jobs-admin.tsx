"use client";

import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
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
  return (
    <>
      <PageHeader
        title="Jobs"
        description="Queue depth and failed scheduled runs. Only safe, allow-listed jobs can be run again."
      />
      {queue ? (
        <p className="mb-6 text-title3">Waiting in queue: {queue.waiting}</p>
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
      <h2 className="text-title3 my-4">Failures</h2>
      {!failures ? (
        <Alert tone="danger" title="Could not load failures">
          Reload to try again.
        </Alert>
      ) : failures.items.length === 0 ? (
        <p>No failed jobs.</p>
      ) : (
        <>
          <TextField
            label="Reason for running again"
            hint="At least 5 characters; saved in the audit log."
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-callout">
              <caption className="sr-only">Failed jobs</caption>
              <thead>
                <tr>
                  <th className="p-2">Date</th>
                  <th className="p-2">Job</th>
                  <th className="p-2">Failure details</th>
                  <th className="p-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {failures.items.map((row) => (
                  <tr key={row.id} className="border-t border-separator">
                    <td className="p-2">{formatUk(row.created_at.slice(0, 10))}</td>
                    <td className="p-2 break-all">{row.job}</td>
                    <td className="p-2 break-all">{JSON.stringify(row.detail)}</td>
                    <td className="p-2">
                      {RERUNNABLE.has(row.job) ? (
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
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <nav aria-label="Job pages" className="mt-6 flex gap-4">
        {offset > 0 && <a href={`/jobs?offset=${Math.max(0, offset - PAGE_SIZE)}`}>Previous</a>}
        {failures && offset + PAGE_SIZE < failures.total && (
          <a href={`/jobs?offset=${offset + PAGE_SIZE}`}>Next</a>
        )}
      </nav>
    </>
  );
}
