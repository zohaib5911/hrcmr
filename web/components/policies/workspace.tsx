"use client";

import { ScrollText } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { ProgressBar } from "@/components/ui/progress";
import { SearchField } from "@/components/ui/search-field";
import { StatusChip } from "@/components/ui/status-chip";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert } from "@/components/ui/alert";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { NewDocumentSheet } from "./new-document-sheet";
import { CATEGORY_LABELS, POLICY_STATUS, percent, type PolicyOut } from "./labels";
import type { components } from "@/lib/api/client";

type PolicyPage = components["schemas"]["PolicyPage"];

/** The Policies list (HR administrators): acceptance progress per document, and New document. */
export function PolicyWorkspace() {
  const can = useCan();
  const mayRead = can("policy.document.read");
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const [data, setData] = useState<PolicyPage | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [version, setVersion] = useState(0);
  const [sheet, setSheet] = useState<{ existing: PolicyOut | null } | null>(null);

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void attempt((c) =>
      c.GET("/policies", {
        params: { query: { search, show_archived: archived, limit: 100 } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) {
        setData(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead, search, archived, version]);

  if (!mayRead) {
    return (
      <EmptyState
        icon={ScrollText}
        title="Policies are for HR administrators"
        description="Your own documents to read and sign are on My documents."
      />
    );
  }

  const columns: Column<PolicyOut>[] = [
    {
      id: "title",
      header: "Policy",
      primary: true,
      sortValue: (row) => row.title,
      cell: (row) => (
        <div className="max-w-80 min-w-0">
          <Link href={`/policies/${row.id}`} className="text-accent-text break-words underline">
            {row.title}
          </Link>
          <p className="text-footnote text-label-secondary">
            {CATEGORY_LABELS[row.category]} · Version {row.version}
          </p>
        </div>
      ),
    },
    {
      id: "status",
      header: "Status",
      sortValue: (row) => row.status,
      cell: (row) => (
        <StatusChip tone={POLICY_STATUS[row.status].tone}>
          {POLICY_STATUS[row.status].label}
        </StatusChip>
      ),
    },
    {
      id: "progress",
      header: "Accepted",
      sortValue: (row) => percent(row.completed, row.recipients),
      cell: (row) =>
        row.status === "draft" ? (
          <span className="text-callout text-label-secondary">Not sent yet</span>
        ) : (
          <div className="flex min-w-40 flex-col gap-1">
            <ProgressBar
              label={`${row.title}: accepted`}
              value={percent(row.completed, row.recipients)}
            />
            <span className="text-footnote text-label-secondary">
              {row.completed} of {row.recipients} done
              {row.overdue > 0 ? ` · ${row.overdue} overdue` : ""}
            </span>
          </div>
        ),
    },
    {
      id: "sent",
      header: "Sent",
      sortValue: (row) => row.sent_at ?? "",
      cell: (row) => (row.sent_at ? formatUk(row.sent_at.slice(0, 10)) : "—"),
    },
  ];

  return (
    <>
      <PageHeader
        title="Policies"
        description="Documents people must read and accept or sign, and who has done so."
        actions={
          <Button variant="filled" onClick={() => setSheet({ existing: null })}>
            New document
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="min-w-64 flex-1">
          <SearchField
            label="Search policies"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Checkbox
          label="Show archived"
          checked={archived}
          onCheckedChange={(value) => setArchived(value === true)}
        />
      </div>
      {problem && <Alert tone="danger" title={problem.message} />}
      <DataTable
        caption="Policies"
        columns={columns}
        rows={data?.items ?? []}
        getRowId={(row) => row.id}
        loading={data === null && !problem}
        empty={
          <EmptyState
            icon={ScrollText}
            title={search ? "No policies match that search" : "No policies yet"}
            description="Create a policy, upload its file, then choose who should read it."
            action={
              search ? undefined : (
                <Button variant="filled" onClick={() => setSheet({ existing: null })}>
                  New document
                </Button>
              )
            }
          />
        }
      />
      {sheet && (
        <NewDocumentSheet
          existing={sheet.existing}
          onOpenChange={(open) => {
            if (!open) setSheet(null);
          }}
          onSaved={() => {
            setSheet(null);
            setVersion((n) => n + 1);
          }}
        />
      )}
    </>
  );
}
