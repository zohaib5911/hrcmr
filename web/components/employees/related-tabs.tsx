"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AttendanceWorkspace } from "@/components/attendance/workspace";
import { BalancePanel } from "@/components/leave/balances";
import { RequestList } from "@/components/leave/home";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { components } from "@/lib/api/schema";
import { attempt, type Problem } from "@/lib/auth/request";

type AuditPage = components["schemas"]["AuditPage"];

export function LeaveTab({ id }: { id: string }) {
  const can = useCan();
  return (
    <div className="flex flex-col gap-6">
      {can("leave.balance.read", "leave.balance.read_own", "leave.balance.read_reports") && (
        <BalancePanel employeeId={id} />
      )}
      {can("leave.request.read", "leave.request.read_own") && <RequestList employeeId={id} />}
    </div>
  );
}

export function AttendanceTab({ id }: { id: string }) {
  const can = useCan();
  return can("attendance.record.read", "attendance.record.read_own") ? (
    <AttendanceWorkspace employeeId={id} profile />
  ) : null;
}

/** Phase 13 replaces this shell with assignments and certificates from Learning. */
export function LearningTab({ id }: { id: string }) {
  const can = useCan();
  return (
    <div className="bg-elevated rounded-card shadow-e1">
      <EmptyState
        icon={BookOpen}
        title="Assigned learning and certificates"
        description="Assigned courses and certificates will appear here when Learning is available."
        action={
          can(
            "learning.assignment.read",
            "learning.assignment.read_own",
            "learning.assignment.read_reports",
          ) ? (
            <Button asChild variant="gray">
              <Link href={"/learning?employee_id=" + id}>Open Learning</Link>
            </Button>
          ) : undefined
        }
      />
    </div>
  );
}

export function ActivityTab({ id }: { id: string }) {
  const [page, setPage] = useState<AuditPage | null>(null);
  const [busy, setBusy] = useState(true);
  const [problem, setProblem] = useState<Problem | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/activity", { params: { path: { employee_id: id } } }),
      );
      if (!active) return;
      setBusy(false);
      if (result.ok) {
        setPage(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [id]);
  async function more() {
    if (!page?.next_cursor || busy) return;
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/employees/{employee_id}/activity", {
        params: { path: { employee_id: id }, query: { cursor: page.next_cursor } },
      }),
    );
    setBusy(false);
    if (result.ok)
      setPage({
        items: [...page.items, ...result.data.items],
        next_cursor: result.data.next_cursor,
      });
    else setProblem(result.problem);
  }
  return (
    <section aria-label="Employee activity" className="flex flex-col gap-4">
      <h2 className="text-headline text-label">Activity</h2>
      {problem && <Alert tone="danger" title={problem.message} />}
      {!page && busy ? (
        <p role="status" className="text-body text-label-secondary">
          Loading activity…
        </p>
      ) : page?.items.length === 0 ? (
        <p className="text-body text-label-secondary">No activity recorded yet.</p>
      ) : null}
      {page && page.items.length > 0 && (
        <ol className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
          {page.items.map((event) => (
            <li key={event.id} className="p-4">
              <p className="text-body text-label">
                {event.action.replaceAll(".", " · ").replaceAll("_", " ")}
              </p>
              <p className="text-caption text-label-secondary">
                {event.actor_name ?? "System"} ·{" "}
                <time dateTime={event.created_at}>
                  {new Date(event.created_at).toLocaleString("en-GB", {
                    timeZone: "Europe/London",
                  })}{" "}
                  (London)
                </time>
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
