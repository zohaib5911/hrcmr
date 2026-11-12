"use client";

import { ScrollText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { ProgressBar } from "@/components/ui/progress";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { attempt, baseUrl, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { NewDocumentSheet } from "./new-document-sheet";
import {
  ACCEPTANCE_STATUS,
  AUDIENCE_LABELS,
  CATEGORY_LABELS,
  MODE_LABELS,
  POLICY_STATUS,
  percent,
  type PolicyOut,
  type PolicyRecipient,
} from "./labels";

/** One policy's acceptance picture: who has accepted, signed, is pending or is overdue. */
export function PolicyDetail({ policyId }: { policyId: string }) {
  const can = useCan();
  const toast = useToast();
  const router = useRouter();
  const mayRead = can("policy.document.read");
  const [policy, setPolicy] = useState<PolicyOut | null>(null);
  const [people, setPeople] = useState<PolicyRecipient[]>([]);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    const path = { params: { path: { policy_id: policyId } } };
    void Promise.all([
      attempt((c) => c.GET("/policies/{policy_id}", path)),
      attempt((c) => c.GET("/policies/{policy_id}/acceptances", path)),
    ]).then(([detail, rows]) => {
      if (!active) return;
      if (!detail.ok) return setProblem(detail.problem);
      setPolicy(detail.data);
      if (rows.ok) setPeople(rows.data);
      setProblem(rows.ok ? null : rows.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead, policyId, version]);

  if (!mayRead) {
    return (
      <EmptyState
        icon={ScrollText}
        title="Policies are for HR administrators"
        description="Your own documents to read and sign are on My documents."
      />
    );
  }
  if (!policy) {
    return problem ? (
      <Alert tone="danger" title={problem.message} />
    ) : (
      <p className="text-callout text-label-secondary">Loading policy…</p>
    );
  }

  const outstanding = policy.recipients - policy.completed;
  const pending = Math.max(0, outstanding - policy.overdue);

  async function remind() {
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/policies/{policy_id}/remind", { params: { path: { policy_id: policyId } } }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    toast.show({
      title:
        result.data.count === 1
          ? "Reminder sent to 1 person"
          : `Reminders sent to ${result.data.count} people`,
      tone: "success",
    });
    setVersion((n) => n + 1);
  }

  async function newVersion() {
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/policies/{policy_id}/new-version", { params: { path: { policy_id: policyId } } }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    router.push(`/policies/${result.data.id}`);
  }

  const columns: Column<PolicyRecipient>[] = [
    {
      id: "person",
      header: "Person",
      primary: true,
      sortValue: (row) => row.employee_name,
      cell: (row) => (
        <span className="break-words">
          {row.employee_name} <span className="text-label-secondary">#{row.employee_number}</span>
        </span>
      ),
    },
    {
      id: "status",
      header: "Status",
      sortValue: (row) => row.status,
      cell: (row) => (
        <StatusChip tone={ACCEPTANCE_STATUS[row.status].tone}>
          {ACCEPTANCE_STATUS[row.status].label}
        </StatusChip>
      ),
    },
    {
      id: "due",
      header: "Due",
      sortValue: (row) => row.due_on ?? "",
      cell: (row) => (row.due_on ? formatUk(row.due_on) : "—"),
    },
    {
      id: "accepted",
      header: "Accepted",
      sortValue: (row) => row.accepted_at ?? "",
      cell: (row) => (row.accepted_at ? formatUk(row.accepted_at.slice(0, 10)) : "—"),
    },
  ];

  return (
    <>
      <Link href="/policies" className="text-callout text-accent-text mb-2 inline-block underline">
        All policies
      </Link>
      <PageHeader
        title={policy.title}
        description={`${CATEGORY_LABELS[policy.category]} · Version ${policy.version}`}
        actions={
          <div className="flex flex-wrap gap-2">
            {policy.status === "draft" && (
              <Button variant="filled" onClick={() => setEditing(true)}>
                Continue setup
              </Button>
            )}
            {policy.status === "sent" && (
              <>
                <Button
                  variant="gray"
                  onClick={() => void remind()}
                  disabled={busy || pending + policy.overdue === 0}
                >
                  Remind pending people
                </Button>
                <Button variant="gray" onClick={() => void newVersion()} disabled={busy}>
                  New version
                </Button>
              </>
            )}
          </div>
        }
      />
      {problem && <Alert tone="danger" title={problem.message} />}
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <StatusChip tone={POLICY_STATUS[policy.status].tone}>
          {POLICY_STATUS[policy.status].label}
        </StatusChip>
        <span className="text-callout text-label-secondary">
          {MODE_LABELS[policy.confirmation_mode]} · {AUDIENCE_LABELS[policy.audience_type]} · Accept
          within {policy.accept_within_days} days
          {policy.auto_send_new_starters ? " · Sent to new starters" : ""}
        </span>
        {policy.file_id && (
          <a
            href={`${baseUrl()}/policies/${policy.id}/view`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-callout text-accent-text underline"
          >
            Open the file
          </a>
        )}
      </div>

      {policy.status !== "draft" && (
        <Card className="mb-6 flex flex-col gap-4 p-5">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Figure label="Recipients" value={policy.recipients} />
            <Figure label="Done" value={policy.completed} />
            <Figure label="Pending" value={pending} />
            <Figure label="Overdue" value={policy.overdue} />
          </div>
          <ProgressBar
            label="Share of recipients who have accepted or signed"
            value={percent(policy.completed, policy.recipients)}
          />
        </Card>
      )}

      <DataTable
        caption="Who has accepted, signed, is pending or is overdue"
        columns={columns}
        rows={people}
        getRowId={(row) => row.employee_id}
        empty={
          <EmptyState
            icon={ScrollText}
            title={policy.status === "draft" ? "Not sent yet" : "No recipients"}
            description={
              policy.status === "draft"
                ? "Continue the setup to choose who receives this document."
                : "Nobody is in this audience."
            }
          />
        }
      />
      {editing && (
        <NewDocumentSheet
          existing={policy}
          onOpenChange={(open) => {
            if (!open) setEditing(false);
          }}
          onSaved={(saved) => {
            setEditing(false);
            if (saved.id !== policyId) router.push(`/policies/${saved.id}`);
            else setVersion((n) => n + 1);
          }}
        />
      )}
    </>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-footnote text-label-secondary">{label}</p>
      <p className="text-title-2 text-label font-semibold tabular-nums">{value}</p>
    </div>
  );
}
