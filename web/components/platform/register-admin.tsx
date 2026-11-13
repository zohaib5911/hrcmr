"use client";

import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable, type Column } from "@/components/ui/data-table";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Status = components["schemas"]["RegisterStatusOut"];
type ImportError = Status["errors"][number];

const ERROR_COLUMNS: readonly Column<ImportError>[] = [
  { id: "date", header: "Date (UTC)", primary: true, cell: (row) => row.created_at },
  {
    id: "detail",
    header: "Failure details",
    cell: (row) => <span className="break-all">{JSON.stringify(row.detail)}</span>,
  },
];
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
          <GroupedList heading="Sponsors" className="mb-6">
            <GroupedRow title="Current sponsors" detail={String(status.current_sponsors)} />
            <GroupedRow title="Total sponsors" detail={String(status.total_sponsors)} />
          </GroupedList>
          {publication ? (
            <GroupedList heading="Latest publication" className="mb-6">
              <GroupedRow title="Published on" detail={formatUk(publication.published_on)} />
              <GroupedRow title="Last import fetched at (UTC)" detail={publication.fetched_at} />
              <GroupedRow title="Rows in publication" detail={String(publication.row_count)} />
              <GroupedRow title="Import status" detail={publication.status} />
            </GroupedList>
          ) : (
            <>
              <h2 className="text-title-3 text-label my-4">Latest publication</h2>
              <p className="text-callout text-label-secondary">
                No register publications imported yet.
              </p>
            </>
          )}
          <h2 className="text-title-3 text-label my-4">Recent import errors</h2>
          {status.errors.length === 0 ? (
            <p className="text-callout text-label-secondary">No recent import errors.</p>
          ) : (
            <DataTable
              caption="Register import failures (latest 20)"
              columns={ERROR_COLUMNS}
              rows={status.errors}
              getRowId={(row) => row.id}
              pageSize={20}
              pager={false}
            />
          )}
        </>
      )}
      <h2 className="text-title-3 text-label my-4">Rerun import</h2>
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
