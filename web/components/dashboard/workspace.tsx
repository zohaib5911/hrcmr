"use client";

import { Check, ChevronRight, Circle, LayoutDashboard } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { KpiCard } from "@/components/ui/kpi-card";
import { ProgressBar } from "@/components/ui/progress";
import { SkeletonCard } from "@/components/ui/skeleton";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Dashboard = components["schemas"]["DashboardOut"];
type Checklist = components["schemas"]["ChecklistOut"];

/** Where each unfinished set-up step is done (keys from the API's checklist, C6.1.12). */
export const STEP_LINKS: Record<string, Route> = {
  company_details: "/company",
  departments_locations: "/company/departments",
  first_employee: "/employees/new",
  first_rtw: "/employees",
  key_personnel: "/company/key-personnel",
};

function StepLabel({ item }: { item: Checklist["items"][number] }) {
  const href = STEP_LINKS[item.key];
  if (item.done || !href) {
    return (
      <span className={item.done ? "text-label-secondary line-through" : ""}>{item.label}</span>
    );
  }
  return (
    <Link
      href={href}
      className="text-accent-text inline-flex items-center gap-1 font-medium hover:underline"
    >
      {item.label}
      <Icon icon={ChevronRight} size={16} />
    </Link>
  );
}

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
export function DashboardWorkspace({ actions }: { actions?: ReactNode }) {
  const can = useCan();
  const [data, setData] = useState<Dashboard | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  // The checklist sits above the cards: both appear in one render, so neither pushes the other down
  // after it is painted (CLS budget, T22.2).
  const [checklistSettled, setChecklistSettled] = useState(false);
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
      if (!active) return;
      if (result.ok) setChecklist(result.data);
      setChecklistSettled(true);
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

  const ready = (checklistSettled && data !== null) || problem !== null;
  const shown = ready ? data : null;
  const hasCards =
    shown !== null &&
    Boolean(
      shown.needs_attention.length ||
      shown.employees ||
      shown.rtw ||
      shown.off_today ||
      shown.approvals ||
      shown.distribution ||
      shown.learning ||
      shown.my_learning ||
      shown.recruitment,
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
        {actions ? <div className="mt-2 flex flex-wrap gap-3">{actions}</div> : null}
      </header>

      {problem ? <Alert tone="danger" title={problem.message} className="mb-6" /> : null}

      {ready && checklist?.visible ? (
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
          <ProgressBar
            value={checklist.total > 0 ? (checklist.done / checklist.total) * 100 : 0}
            label="Set-up progress"
          />
          <ul className="flex flex-col gap-2">
            {checklist.items.map((item) => (
              <li key={item.key} className="text-body text-label flex items-center gap-2">
                <Icon icon={item.done ? Check : Circle} size={16} />
                <StepLabel item={item} />
                <span className="sr-only">{item.done ? "(done)" : "(to do)"}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {shown === null && !problem ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <SkeletonCard className="h-40" />
          <SkeletonCard className="h-40" />
          <SkeletonCard className="h-40" />
        </div>
      ) : null}

      {shown ? (
        <>
          {shown.employees || shown.rtw ? (
            <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {shown.employees ? (
                <>
                  <KpiCard label="Employees" value={shown.employees.active} />
                  <KpiCard label="On leave" value={shown.employees.on_leave} />
                </>
              ) : null}
              {shown.rtw ? (
                <>
                  <KpiCard label="Right to Work coverage (%)" value={shown.rtw.coverage_percent} />
                  <KpiCard label="Checks current" value={shown.rtw.verified} />
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
            {shown.needs_attention.length > 0 ? (
              <Card title="Needs attention">
                <ul className="flex flex-col gap-2">
                  {shown.needs_attention.map((item) => (
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

            {shown.rtw ? (
              <Card title="Right to Work coverage">
                <p className="text-callout text-label">
                  {shown.rtw.verified} of {shown.rtw.checked} people have a current check.
                </p>
                <p className="text-footnote text-label-secondary">
                  Expiring {shown.rtw.expiring} · Expired {shown.rtw.expired} · Evidence missing{" "}
                  {shown.rtw.evidence_missing} · Not recorded {shown.rtw.not_recorded}
                </p>
                <Link href="/employees?rtw=Expiring" className="text-callout text-accent">
                  Review Right to Work
                </Link>
              </Card>
            ) : null}

            {shown.off_today ? (
              <Card title="Who is off">
                <p className="text-callout text-label">{shown.off_today.count} on leave now</p>
                <p className="text-footnote text-label-secondary">
                  {shown.off_today.names.join(", ") || "Nobody"}
                </p>
              </Card>
            ) : null}

            {shown.approvals ? (
              <Card title="Approvals">
                <p className="text-callout text-label">
                  {shown.approvals.pending} leave request(s) waiting for a decision
                </p>
                <Link href="/leave" className="text-callout text-accent">
                  Open leave
                </Link>
              </Card>
            ) : null}

            {shown.distribution ? (
              <Card title="Employee distribution">
                {shown.distribution.rows.length === 0 ? (
                  <p className="text-callout text-label-secondary">No employees yet</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {shown.distribution.rows.map((row) => (
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

            {shown.learning || shown.my_learning ? (
              <Card title="Learning">
                {shown.learning ? (
                  <p className="text-callout text-label">
                    {shown.learning.overdue} courses overdue
                  </p>
                ) : null}
                {shown.my_learning ? (
                  <p className="text-callout text-label">
                    You have {shown.my_learning.open} open
                    {shown.my_learning.overdue ? `, ${shown.my_learning.overdue} overdue` : ""}.
                  </p>
                ) : null}
                <Link href="/learning" className="text-callout text-accent">
                  Open learning
                </Link>
              </Card>
            ) : null}

            {shown.recruitment ? (
              <Card title="Recruitment">
                <p className="text-callout text-label">
                  {shown.recruitment.latest.join(", ") || "No candidates yet"}
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
