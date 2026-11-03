"use client";

import { useEffect, useState } from "react";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { ACTIVITY_CATEGORIES, type ActivityCategory } from "@/lib/compliance/hub";
import { sentTime } from "@/lib/compliance/reminders";

type AuditPage = components["schemas"]["AuditPage"];

export function HubActivity() {
  const can = useCan();
  const [category, setCategory] = useState<ActivityCategory>("all");
  const [page, setPage] = useState<AuditPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/compliance/activity", { params: { query: { category } } }),
      );
      if (!active) return;
      if (result.ok) {
        setPage(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [category]);
  async function more() {
    if (!page?.next_cursor) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.GET("/compliance/activity", { params: { query: { category, cursor: page.next_cursor } } }),
    );
    setBusy(false);
    if (result.ok)
      setPage({
        items: [...page.items, ...result.data.items],
        next_cursor: result.data.next_cursor,
      });
    else setProblem(result.problem);
  }
  async function exportCsv() {
    setExporting(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/compliance/activity.csv", { params: { query: { category } }, parseAs: "blob" }),
    );
    setExporting(false);
    if (!result.ok) return setProblem(result.problem);
    const url = URL.createObjectURL(result.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "compliance-activity.csv";
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section aria-label="Compliance activity" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-title-3 text-label">Activity</h2>
        {can("compliance.audit.export") && (
          <Button variant="gray" loading={exporting} onClick={() => void exportCsv()}>
            Export CSV
          </Button>
        )}
      </div>
      <Select
        label="Activity category"
        value={category}
        disabled={busy}
        onChange={(e) => {
          setCategory(e.target.value as ActivityCategory);
          setPage(null);
        }}
        containerClassName="sm:w-64"
      >
        {ACTIVITY_CATEGORIES.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </Select>
      {problem && <Alert tone="danger" title={problem.message} />}
      {!page && !problem && (
        <p role="status" className="text-body text-label-secondary">
          Loading activity…
        </p>
      )}
      {page?.items.length === 0 && (
        <p className="text-body text-label-secondary">No activity in this category.</p>
      )}
      {page && page.items.length > 0 && (
        <ol className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
          {page.items.map((event) => (
            <li key={event.id} className="p-4">
              <p className="text-body text-label break-words">
                {event.action.replaceAll(".", " · ").replaceAll("_", " ")}
              </p>
              <p className="text-caption text-label-secondary">
                {event.actor_name ?? "System"} ·{" "}
                <time dateTime={event.created_at}>{sentTime(event.created_at)}</time>
              </p>
              {event.summary && (
                <p className="text-callout text-label-secondary mt-1 break-words">
                  {event.summary}
                </p>
              )}
              {event.reason && (
                <p className="text-callout text-label-secondary mt-1 break-words">
                  Reason: {event.reason}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
      {page?.next_cursor && (
        <Button variant="gray" loading={busy} onClick={() => void more()}>
          Load more activity
        </Button>
      )}
    </section>
  );
}
