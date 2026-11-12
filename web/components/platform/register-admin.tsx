"use client";

import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Status = components["schemas"]["RegisterStatusOut"];
export function RegisterAdmin({ status }: { status: Status | null }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [denied, setDenied] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const publication = status?.last_publication;
  // Both owner and support admins can read status and run imports. The API enforces
  // platform.jobs.run again; unavailable status or a refused action disables reruns.
  const canRun = status !== null && !denied;
  const validReason = reason.trim().length >= 5 && reason.trim().length <= 500;
  async function rerun() {
    if (!canRun || busy || !validReason) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await attempt((c) =>
        c.POST("/platform/register/run", { body: { reason: reason.trim() } }),
      );
      if (result.ok) setNotice("Register import queued. Reload later to see the latest status.");
      else {
        setError(result.problem.message);
        if (["UNAUTHENTICATED", "FORBIDDEN"].includes(result.problem.code)) setDenied(true);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title="Sponsor register"
        description="Import status and recent errors for the sponsor register."
      />
      {!status ? (
        <Alert tone="danger" title="Could not load register status">
          Reload to try again.
        </Alert>
      ) : (
        <>
          <dl className="mb-6 grid gap-3 sm:grid-cols-2">
            <div>
              <dt>Current sponsors</dt>
              <dd>{status.current_sponsors}</dd>
            </div>
            <div>
              <dt>Total sponsors</dt>
              <dd>{status.total_sponsors}</dd>
            </div>
          </dl>
          <h2 className="text-title3 my-4">Latest publication</h2>
          {publication ? (
            <dl className="mb-6 grid gap-3 sm:grid-cols-2">
              <div>
                <dt>Published on</dt>
                <dd>{formatUk(publication.published_on)}</dd>
              </div>
              <div>
                <dt>Last import fetched at (UTC)</dt>
                <dd>{publication.fetched_at}</dd>
              </div>
              <div>
                <dt>Rows in publication</dt>
                <dd>{publication.row_count}</dd>
              </div>
              <div>
                <dt>Import status</dt>
                <dd>{publication.status}</dd>
              </div>
            </dl>
          ) : (
            <p>No register publications imported yet.</p>
          )}
          <h2 className="text-title3 my-4">Recent import errors</h2>
          {status.errors.length === 0 ? (
            <p>No recent import errors.</p>
          ) : (
            <div
              className="overflow-x-auto"
              tabIndex={0}
              role="region"
              aria-label="Recent import errors"
            >
              <table className="w-full text-left text-callout">
                <caption className="sr-only">Register import failures (latest 20)</caption>
                <thead>
                  <tr>
                    <th className="p-2">Date (UTC)</th>
                    <th className="p-2">Failure details</th>
                  </tr>
                </thead>
                <tbody>
                  {status.errors.map((row) => (
                    <tr key={row.id} className="border-t border-separator">
                      <td className="p-2">{row.created_at}</td>
                      <td className="p-2 break-all">{JSON.stringify(row.detail)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <h2 className="text-title3 my-4">Rerun import</h2>
      {error && (
        <Alert tone="danger" title="Could not queue import">
          {error}
        </Alert>
      )}
      {denied && <a href="/session?next=%2Fregister">Start a new platform session</a>}
      {notice && (
        <Alert tone="success" title="Import queued">
          {notice}
        </Alert>
      )}
      <TextField
        label="Reason for rerunning import"
        hint="At least 5 characters; saved in the audit log."
        maxLength={500}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        disabled={!canRun || busy}
      />
      <div className="mt-4">
        <ConfirmDialog
          trigger={
            <Button variant="gray" disabled={!canRun || busy || !validReason}>
              Rerun import
            </Button>
          }
          title="Rerun sponsor register import?"
          description="This queues a safe import from the configured official source. Unchanged data is skipped and the action is audited."
          confirmLabel="Queue import"
          confirmDisabled={!canRun || busy || !validReason}
          onConfirm={rerun}
        />
      </div>
    </>
  );
}
