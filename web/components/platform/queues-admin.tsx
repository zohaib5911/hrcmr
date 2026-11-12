"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Select } from "@/components/ui/select";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { PAGE_SIZE, Pager } from "./pager";

type DeletionRow = components["schemas"]["DeletionRequestRow"];
type ExportRow = components["schemas"]["DataExportRow"];

const DELETION_STATUSES = ["awaiting_code", "scheduled", "withdrawn", "completed"] as const;
const EXPORT_STATUSES = ["queued", "ready", "failed"] as const;
type DeletionStatus = (typeof DELETION_STATUSES)[number];
type ExportStatus = (typeof EXPORT_STATUSES)[number];

const label = (status: string) => status.replace(/_/g, " ");
const day = (iso: string | null) => (iso ? formatUk(iso.slice(0, 10)) : "–");

/** Platform queues: company deletion requests and data exports, each filtered by status (read only). */
export function QueuesAdmin() {
  const [deletionStatus, setDeletionStatus] = useState<DeletionStatus | "">("");
  const [exportStatus, setExportStatus] = useState<ExportStatus | "">("");
  const [deletionOffset, setDeletionOffset] = useState(0);
  const [exportOffset, setExportOffset] = useState(0);
  const [deletionsLoaded, setDeletions] = useState<{
    key: string;
    items: DeletionRow[];
    total: number;
  } | null>(null);
  const [exportsLoaded, setExports] = useState<{
    key: string;
    items: ExportRow[];
    total: number;
  } | null>(null);
  // Rows count as loading until they match the chosen filter and page.
  const deletionKey = `${deletionStatus}:${deletionOffset}`;
  const exportKey = `${exportStatus}:${exportOffset}`;
  const deletions = deletionsLoaded?.key === deletionKey ? deletionsLoaded.items : null;
  const exports = exportsLoaded?.key === exportKey ? exportsLoaded.items : null;
  const [problem, setProblem] = useState<Problem | null>(null);

  const fail = useCallback((p: Problem) => {
    // An expired platform session: start again and come back here.
    if (p.code === "UNAUTHENTICATED" || p.code === "FORBIDDEN") {
      window.location.replace(`/session?next=${encodeURIComponent("/queues")}`);
      return;
    }
    setProblem(p);
  }, []);

  useEffect(() => {
    let live = true;
    void attempt((c) =>
      c.GET("/platform/deletion-requests", {
        params: {
          query: {
            limit: PAGE_SIZE,
            offset: deletionOffset,
            ...(deletionStatus ? { status: deletionStatus } : {}),
          },
        },
      }),
    ).then((r) => {
      if (!live) return;
      if (r.ok)
        setDeletions({
          key: `${deletionStatus}:${deletionOffset}`,
          items: r.data.items,
          total: r.data.total,
        });
      else fail(r.problem);
    });
    return () => {
      live = false;
    };
  }, [deletionStatus, deletionOffset, fail]);

  useEffect(() => {
    let live = true;
    void attempt((c) =>
      c.GET("/platform/data-exports", {
        params: {
          query: {
            limit: PAGE_SIZE,
            offset: exportOffset,
            ...(exportStatus ? { status: exportStatus } : {}),
          },
        },
      }),
    ).then((r) => {
      if (!live) return;
      if (r.ok)
        setExports({
          key: `${exportStatus}:${exportOffset}`,
          items: r.data.items,
          total: r.data.total,
        });
      else fail(r.problem);
    });
    return () => {
      live = false;
    };
  }, [exportStatus, exportOffset, fail]);

  return (
    <>
      <PageHeader
        title="Deletion and export queues"
        description="Company deletion requests and data exports, with where each one stands."
      />
      {problem ? (
        <Alert tone="danger" title="That did not load" className="mb-6">
          {problem.message}
        </Alert>
      ) : null}

      <section aria-labelledby="deletions-h" className="mb-10">
        <h2 id="deletions-h" className="text-title3 mb-3">
          Deletion requests
        </h2>
        <Select
          label="Status"
          value={deletionStatus}
          onChange={(e) => {
            setDeletionOffset(0);
            setDeletionStatus(e.target.value as DeletionStatus | "");
          }}
          containerClassName="mb-4 max-w-xs"
        >
          <option value="">All</option>
          {DELETION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </Select>
        {deletions === null ? (
          <p className="text-callout text-label-secondary">Loading…</p>
        ) : deletions.length === 0 ? (
          <p className="text-callout text-label-secondary">No deletion requests.</p>
        ) : (
          <ul className="grid gap-3" aria-label="Deletion requests">
            {deletions.map((d) => (
              <li key={d.id} className="border-separator rounded-xl border p-4">
                <p className="text-callout break-words font-medium">{d.company_name}</p>
                <p className="text-footnote text-label-secondary">
                  {label(d.status)} · requested {day(d.requested_at)}
                  {d.scheduled_for ? ` · deletes ${day(d.scheduled_for)}` : ""}
                  {d.export_requested ? " · export requested" : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
        <Pager
          label="Deletion requests"
          offset={deletionOffset}
          total={deletionsLoaded?.total ?? 0}
          onChange={setDeletionOffset}
        />
      </section>

      <section aria-labelledby="exports-h">
        <h2 id="exports-h" className="text-title3 mb-3">
          Data exports
        </h2>
        <Select
          label="Status"
          value={exportStatus}
          onChange={(e) => {
            setExportOffset(0);
            setExportStatus(e.target.value as ExportStatus | "");
          }}
          containerClassName="mb-4 max-w-xs"
        >
          <option value="">All</option>
          {EXPORT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </Select>
        {exports === null ? (
          <p className="text-callout text-label-secondary">Loading…</p>
        ) : exports.length === 0 ? (
          <p className="text-callout text-label-secondary">No data exports.</p>
        ) : (
          <ul className="grid gap-3" aria-label="Data exports">
            {exports.map((x) => (
              <li key={x.id} className="border-separator rounded-xl border p-4">
                <p className="text-callout break-words font-medium">{x.company_name}</p>
                <p className="text-footnote text-label-secondary">
                  {label(x.status)} · requested {day(x.requested_at)}
                  {x.finished_at ? ` · finished ${day(x.finished_at)}` : ""}
                  {x.error_code ? ` · ${x.error_code}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
        <Pager
          label="Data exports"
          offset={exportOffset}
          total={exportsLoaded?.total ?? 0}
          onChange={setExportOffset}
        />
      </section>
    </>
  );
}
