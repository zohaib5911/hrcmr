"use client";

import { Check, Circle, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { KpiCard } from "@/components/ui/kpi-card";
import { SkeletonCard } from "@/components/ui/skeleton";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Dashboard = components["schemas"]["DashboardOut"];
type Checklist = components["schemas"]["ChecklistOut"];

function greeting(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section
      aria-label={title}
      className="bg-elevated border-separator rounded-card flex flex-col gap-3 border p-4"
    >
      <h2 className="text-headline text-label">{title}</h2>
      {children}
    </section>
  );
}

/** The home page: a greeting, the company's headline numbers, cards the person may see, and the set-up
 * checklist until it is finished or dismissed (plan 8.2). */
export function DashboardWorkspace() {
  const can = useCan();
  const [data, setData] = useState<Dashboard | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [hour] = useState(() => new Date().getHours());

  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/dashboard")).then((result) => {
      if (!active) return;
      if (result.ok) setData(result.data);
      else setProblem(result.problem);
    });
    // Only company administrators may set up the company; for everyone else the checklist is hidden.
    void attempt((c) => c.GET("/onboarding/checklist")).then((result) => {
      if (active && result.ok) setChecklist(result.data);
    });
    return () => {
      active = false;
    };
  }, []);

  async function dismiss() {
    const result = await attempt((c) => c.POST("/onboarding/checklist/dismiss"));
    if (result.ok) setChecklist((list) => (list ? { ...list, visible: false } : list));
    else setProblem(result.problem);
  }

  const hasCards =
    data !== null &&
    Boolean(
      data.needs_attention.length ||
      data.employees ||
      data.rtw ||
      data.off_today ||
      data.approvals ||
      data.distribution ||
      data.learning ||
      data.my_learning ||
      data.recruitment,
    );

  const quick = [
    { href: "/employees/new", label: "Add employee", show: can("employee.profile.write") },
    { href: "/recruitment", label: "Add candidate", show: can("recruitment.candidate.write") },
    { href: "/my-leave", label: "Request leave", show: can("leave.request.create_own") },
    { href: "/documents", label: "Upload document", show: can("document.file.write") },
  ].filter((item) => item.show);

  return (
    <>
      <header className="mb-6 flex flex-col gap-2">
        <h1 className="text-large-title text-label">Dashboard</h1>
        <p className="text-title-3 text-label" suppressHydrationWarning>
          {greeting(hour)}
          {data ? `, ${data.first_name}` : ""}
        </p>
        <p className="text-callout text-label-secondary">
          {data ? data.status_line : "Loading your day"}
        </p>
        {quick.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {quick.map((item) => (
              <Button key={item.href} variant="gray" size="sm" asChild>
                <Link href={item.href}>{item.label}</Link>
              </Button>
            ))}
          </div>
        ) : null}
      </header>

      {problem ? <Alert tone="danger" title={problem.message} className="mb-6" /> : null}

      {checklist?.visible ? (
        <section
          aria-label="Get set up"
          className="bg-elevated border-separator rounded-card mb-6 flex flex-col gap-3 border p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-headline text-label">Get set up</h2>
            <Button variant="plain" size="sm" onClick={dismiss}>
              Dismiss
            </Button>
          </div>
          <p className="text-footnote text-label-secondary">
            {checklist.done} of {checklist.total} done
          </p>
          <progress
            className="h-2 w-full"
            value={checklist.done}
            max={checklist.total}
            aria-label="Set-up progress"
          />
          <ul className="flex flex-col gap-2">
            {checklist.items.map((item) => (
              <li key={item.key} className="text-body text-label flex items-center gap-2">
                <Icon icon={item.done ? Check : Circle} size={16} />
                <span className={item.done ? "text-label-secondary line-through" : ""}>
                  {item.label}
                </span>
                <span className="sr-only">{item.done ? "(done)" : "(to do)"}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data === null && !problem ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <SkeletonCard className="h-40" />
          <SkeletonCard className="h-40" />
          <SkeletonCard className="h-40" />
        </div>
      ) : null}

      {data ? (
        <>
          {data.employees || data.rtw ? (
            <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {data.employees ? (
                <>
                  <KpiCard label="Employees" value={data.employees.active} />
                  <KpiCard label="On leave" value={data.employees.on_leave} />
                </>
              ) : null}
              {data.rtw ? (
                <>
                  <KpiCard label="Right to Work coverage (%)" value={data.rtw.coverage_percent} />
                  <KpiCard label="Checks current" value={data.rtw.verified} />
                </>
              ) : null}
            </div>
          ) : null}

          {!hasCards ? (
            <EmptyState
              icon={LayoutDashboard}
              title="Nothing to show yet"
              description="Cards appear here as your company adds people, courses and records."
            />
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.needs_attention.length > 0 ? (
              <Card title="Needs attention">
                <ul className="flex flex-col gap-2">
                  {data.needs_attention.map((item) => (
                    <li key={item.label} className="flex items-center justify-between gap-2">
                      <span className="text-body text-label">{item.label}</span>
                      <Button variant="gray" size="sm" asChild>
                        <Link href={item.link}>{item.count}</Link>
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}

            {data.rtw ? (
              <Card title="Right to Work coverage">
                <p className="text-callout text-label">
                  {data.rtw.verified} of {data.rtw.checked} people have a current check.
                </p>
                <p className="text-footnote text-label-secondary">
                  Expiring {data.rtw.expiring} · Expired {data.rtw.expired} · Evidence missing{" "}
                  {data.rtw.evidence_missing} · Not recorded {data.rtw.not_recorded}
                </p>
                <Link href="/employees?rtw=Expiring" className="text-callout text-accent">
                  Review Right to Work
                </Link>
              </Card>
            ) : null}

            {data.off_today ? (
              <Card title="Who is off">
                <p className="text-callout text-label">{data.off_today.count} on leave now</p>
                <p className="text-footnote text-label-secondary">
                  {data.off_today.names.join(", ") || "Nobody"}
                </p>
              </Card>
            ) : null}

            {data.approvals ? (
              <Card title="Approvals">
                <p className="text-callout text-label">
                  {data.approvals.pending} leave request(s) waiting for a decision
                </p>
                <Link href="/leave" className="text-callout text-accent">
                  Open leave
                </Link>
              </Card>
            ) : null}

            {data.distribution ? (
              <Card title="Employee distribution">
                {data.distribution.rows.length === 0 ? (
                  <p className="text-callout text-label-secondary">No employees yet</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {data.distribution.rows.map((row) => (
                      <li
                        key={row.department}
                        className="text-body text-label flex justify-between"
                      >
                        <span>{row.department}</span>
                        <span className="text-label-secondary">{row.headcount}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            ) : null}

            {data.learning || data.my_learning ? (
              <Card title="Learning">
                {data.learning ? (
                  <p className="text-callout text-label">{data.learning.overdue} courses overdue</p>
                ) : null}
                {data.my_learning ? (
                  <p className="text-callout text-label">
                    You have {data.my_learning.open} open
                    {data.my_learning.overdue ? `, ${data.my_learning.overdue} overdue` : ""}.
                  </p>
                ) : null}
                <Link href="/learning" className="text-callout text-accent">
                  Open learning
                </Link>
              </Card>
            ) : null}

            {data.recruitment ? (
              <Card title="Recruitment">
                <p className="text-callout text-label">
                  {data.recruitment.latest.join(", ") || "No candidates yet"}
                </p>
                <Link href="/recruitment" className="text-callout text-accent">
                  Open recruitment
                </Link>
              </Card>
            ) : null}
          </div>
        </>
      ) : null}
    </>
  );
}
