"use client";

import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

type Version = components["schemas"]["RulesVersionOut"];

type Change = { key: string; field: string; from: unknown; to: unknown };
type Section = { added: string[]; removed: string[]; changed: Change[] };
type Diff = {
  against?: { id: string; name: string } | null;
  counts?: Record<string, number>;
  sections?: Record<string, Section>;
  has_changes?: boolean;
  note?: string;
};

const TONE = { live: "success", draft: "warning", retired: "neutral" } as const;
const LABEL = { live: "Live", draft: "Draft", retired: "Retired" } as const;
const MAX_CHANGES = 12;

function asDiff(value: unknown): Diff {
  return (value && typeof value === "object" ? value : {}) as Diff;
}

function show(value: unknown): string {
  if (value === null || value === undefined) return "none";
  return typeof value === "string" ? value : JSON.stringify(value);
}

/** The draft against the live version: rows added, removed and changed, table by table. */
function DiffSummary({ diff }: { diff: Diff }) {
  if (diff.note) return <p className="text-callout text-label-secondary">{diff.note}</p>;
  if (!diff.has_changes) {
    return (
      <p className="text-callout text-label-secondary">
        No rate or rule changed. Only the page bytes differ.
      </p>
    );
  }
  return (
    <div className="grid gap-4">
      {Object.entries(diff.sections ?? {}).map(([table, section]) => {
        const total = section.added.length + section.removed.length + section.changed.length;
        if (total === 0) return null;
        return (
          <section key={table} aria-label={table.replace(/_/g, " ")} className="grid gap-2">
            <h3 className="text-callout font-medium">
              {table.replace(/_/g, " ")}: {section.added.length} added, {section.removed.length}{" "}
              removed, {section.changed.length} changed
            </h3>
            <ul className="text-footnote text-label-secondary grid gap-1">
              {section.changed.slice(0, MAX_CHANGES).map((change) => (
                <li key={`${change.key}-${change.field}`}>
                  {change.key} · {change.field}: {show(change.from)} → {show(change.to)}
                </li>
              ))}
            </ul>
            {section.changed.length > MAX_CHANGES ? (
              <p className="text-footnote text-label-secondary">
                And {section.changed.length - MAX_CHANGES} more changes.
              </p>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}

type Props = { versions: Version[] };

/** The SOC rules versions: the live one, a draft to review, and earlier ones to restore. */
export function RulesEditor({ versions: initial }: Props) {
  const [versions, setVersions] = useState<Version[]>(initial);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const live = versions.find((v) => v.status === "live") ?? null;
  const draft = versions.find((v) => v.status === "draft") ?? null;
  const earlier = versions.filter((v) => v.status === "retired");

  async function reload() {
    const result = await attempt((c) => c.GET("/platform/rules"));
    if (result.ok) setVersions(result.data.items);
    else setProblem(result.problem);
  }

  async function act(id: string, action: "publish" | "rollback", done: string) {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    const result = await attempt((c) =>
      action === "publish"
        ? c.POST("/platform/rules/{version_id}/publish", { params: { path: { version_id: id } } })
        : c.POST("/platform/rules/{version_id}/rollback", { params: { path: { version_id: id } } }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    setNotice(done);
    await reload();
  }

  return (
    <>
      <PageHeader
        title="SOC rules"
        description="The GOV.UK tables behind the sponsorship checker. A daily check adds a draft when a page changes. Publish it here after you have read the changes."
      />
      {problem ? (
        <Alert tone="danger" title="That did not work" className="mb-6">
          {problem.message}
        </Alert>
      ) : null}
      {notice ? (
        <Alert tone="success" title={notice} className="mb-6">
          The checks saved before this change keep the rules they were made with.
        </Alert>
      ) : null}
      <div className="grid gap-6">
        <Card>
          <CardHeader
            title="Live version"
            headingLevel={2}
            actions={live ? <StatusChip tone={TONE.live}>{LABEL.live}</StatusChip> : null}
          />
          <CardBody className="grid gap-2 pb-5">
            {live ? (
              <>
                <p className="text-callout">{live.name}</p>
                <p className="text-footnote text-label-secondary">
                  Effective {formatUk(live.effective_from)}
                  {live.published_at
                    ? `, published ${formatUk(live.published_at.slice(0, 10))}`
                    : ""}
                </p>
              </>
            ) : (
              <p className="text-callout text-label-secondary">
                No version is live yet. The owner imports and publishes the first one.
              </p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Draft waiting for review"
            description="Read the changes before you publish. Publishing makes this the live version."
            headingLevel={2}
            actions={draft ? <StatusChip tone={TONE.draft}>{LABEL.draft}</StatusChip> : null}
          />
          <CardBody className="grid gap-4 pb-5">
            {draft ? (
              <>
                <p className="text-callout">{draft.name}</p>
                <DiffSummary diff={asDiff(draft.diff_summary)} />
                <div>
                  <ConfirmDialog
                    trigger={<Button disabled={busy}>Publish this version</Button>}
                    title="Publish this rules version?"
                    description="The current live version is retired. Checks already saved keep the rules they were made with."
                    confirmLabel="Publish"
                    onConfirm={() => act(draft.id, "publish", "Rules version published.")}
                  />
                </div>
              </>
            ) : (
              <p className="text-callout text-label-secondary">
                Nothing to review. A draft appears here when a GOV.UK page changes.
              </p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Earlier versions" headingLevel={2} />
          <CardBody className="grid gap-3 pb-5">
            {earlier.length === 0 ? (
              <p className="text-callout text-label-secondary">No earlier versions.</p>
            ) : (
              <ul className="grid gap-2">
                {earlier.map((version) => (
                  <li
                    key={version.id}
                    className="bg-elevated rounded-card shadow-e1 flex flex-wrap items-center justify-between gap-3 p-3"
                  >
                    <span className="text-callout">
                      {version.name}
                      <span className="text-footnote text-label-secondary block">
                        Effective {formatUk(version.effective_from)}
                      </span>
                    </span>
                    <ConfirmDialog
                      trigger={
                        <Button variant="gray" size="sm" disabled={busy}>
                          Restore this version
                        </Button>
                      }
                      title="Restore this rules version?"
                      description="It becomes the live version and the current live version is retired. Checks already saved keep the rules they were made with."
                      confirmLabel="Restore"
                      onConfirm={() => act(version.id, "rollback", "Rules version restored.")}
                    />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
