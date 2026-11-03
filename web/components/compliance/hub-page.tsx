"use client";

import { Building2, FileCheck2, FolderOpen, ShieldCheck, Users, ClipboardList } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { EXPIRY_BUCKETS, type Overview } from "@/lib/compliance/hub";
import { shortDate } from "@/lib/employees/profile";
import { HubActivity } from "./hub-activity";

const TOOLS = [
  ["Company Profile", "/company", Building2, "company.overview.read"],
  [
    "Sponsored employees",
    "/sponsor-compliance/migrant-employees",
    Users,
    "compliance.overview.read",
  ],
  [
    "Change of Circumstances",
    "/sponsor-compliance/change-of-circumstances",
    ClipboardList,
    "employee.change_of_circumstances.read",
  ],
  ["Key Personnel", "/company/key-personnel", ShieldCheck, "company.profile.read"],
  [
    "Company compliance documents",
    "/company/compliance-documents",
    FileCheck2,
    "company.profile.read",
  ],
  [
    "Sponsor Management Dossier",
    "/sponsor-compliance/dossier",
    FolderOpen,
    "compliance.overview.read",
  ],
] as const;

export function HubPage({ overview }: { overview: Overview }) {
  const can = useCan();
  const [documentType, setDocumentType] = useState("all");
  const complete = overview.readiness.filter((check) => check.status === "complete").length;
  const notApplicable = overview.readiness.filter(
    (check) => check.status === "not_applicable",
  ).length;
  const types = [
    ...new Map(
      overview.expiring.map((item) => [
        item.document_type,
        item.document_type === "company" ? "Company documents" : item.document_label,
      ]),
    ).entries(),
  ];
  return (
    <>
      <PageHeader
        title="Sponsor compliance"
        description="Checks, documents and reporting duties that need your attention."
        actions={
          <>
            <Button variant="gray" asChild>
              <a
                href="https://www.gov.uk/check-job-applicant-right-to-work"
                target="_blank"
                rel="noopener noreferrer"
              >
                Check right to work on GOV.UK<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </Button>
            <Button asChild>
              <Link href="/sponsor-compliance/reminders">Compliance Reminders</Link>
            </Button>
          </>
        }
      />
      <div className="flex flex-col gap-8">
        <section aria-label="Needs attention" className="flex flex-col gap-3">
          <h2 className="text-title-3 text-label">
            Needs attention{" "}
            <span className="text-label-secondary">({overview.attention.length})</span>
          </h2>
          {overview.attention.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="Nothing needs attention"
              description="Keep checks and documents up to date as circumstances change."
            />
          ) : (
            <ul className="bg-elevated rounded-card shadow-e1 divide-separator divide-y">
              {overview.attention.map((item) => (
                <li
                  key={item.id}
                  className="flex flex-col items-start justify-between gap-3 p-4 sm:flex-row sm:items-center"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-headline text-label break-words">{item.title}</p>
                    <p className="text-callout text-label-secondary">
                      {item.detail}
                      {item.due_on ? " · " + shortDate(item.due_on) : ""}
                    </p>
                  </div>
                  <Button variant={item.priority === 0 ? "tinted" : "gray"} size="sm" asChild>
                    <Link href={item.href as Route}>
                      {item.action}
                      <span className="sr-only"> · {item.detail}</span>
                    </Link>
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="RTW coverage"
              headingLevel={2}
              description="Valid checks include those with a follow-up due soon."
            />
            <CardBody>
              <p className="text-title-2 text-label tabular-nums">
                {overview.coverage.valid} of {overview.coverage.total} hold a valid check
              </p>
              <ul className="mt-4 grid grid-cols-2 gap-3">
                {overview.coverage.counts.map((count) => (
                  <li key={count.status}>
                    <Link
                      className="text-callout text-accent-text underline hit-target inline-flex items-center"
                      href={count.href as Route}
                    >
                      {count.label}: {count.count}
                    </Link>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
          <Card>
            <CardHeader
              title="Inspection readiness"
              headingLevel={2}
              description={`${complete} of 5 complete${notApplicable ? " · " + notApplicable + " not applicable" : ""}`}
            />
            <CardBody>
              <ul className="flex flex-col gap-4">
                {overview.readiness.map((check) => (
                  <li key={check.id}>
                    <div className="flex flex-wrap gap-2 items-center">
                      <Link
                        className="text-callout text-accent-text underline"
                        href={check.href as Route}
                      >
                        {check.title}
                      </Link>
                      <StatusChip
                        tone={
                          check.status === "complete"
                            ? "success"
                            : check.status === "incomplete"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {check.status === "complete"
                          ? "Complete"
                          : check.status === "incomplete"
                            ? "To do"
                            : "Not applicable"}
                      </StatusChip>
                    </div>
                    <p className="text-caption text-label-secondary mt-1">{check.detail}</p>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
        <section aria-label="Expiring in the next 90 days" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-title-3 text-label">Expiring in the next 90 days</h2>
            <Select
              label="Document type"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              containerClassName="w-full sm:w-64"
            >
              <option value="all">All document types</option>
              {types.map(([type, label]) => (
                <option key={type} value={type}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {EXPIRY_BUCKETS.map(([bucket, label]) => {
              const items = overview.expiring.filter(
                (item) =>
                  item.bucket === bucket &&
                  (documentType === "all" || item.document_type === documentType),
              );
              return (
                <Card key={bucket}>
                  <CardHeader title={label + " (" + items.length + ")"} />
                  <CardBody>
                    {items.length === 0 ? (
                      <p className="text-callout text-label-secondary">No documents.</p>
                    ) : (
                      <ul className="flex flex-col gap-4">
                        {items.map((item) => (
                          <li key={item.id}>
                            <Link
                              href={item.href as Route}
                              className="text-callout text-accent-text underline"
                            >
                              {item.employee_name} · {item.document_label}
                            </Link>
                            <p className="text-caption text-label-secondary">
                              {shortDate(item.expires_on)} ·{" "}
                              {item.days_left < 0
                                ? `${-item.days_left} days overdue`
                                : `${item.days_left} days left`}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardBody>
                </Card>
              );
            })}
          </div>
        </section>
        {can("compliance.audit.read") && <HubActivity />}
        <section aria-label="Compliance tools" className="flex flex-col gap-4">
          <h2 className="text-title-3 text-label">Compliance tools</h2>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {TOOLS.filter(([, , , permission]) => can(permission)).map(([title, href, icon]) => (
              <li key={href}>
                <Link
                  href={href as Route}
                  className="bg-elevated rounded-card shadow-e1 flex items-center gap-3 p-5 text-body text-label hover:bg-fill-secondary hit-target"
                >
                  <Icon icon={icon} className="text-label-secondary" />
                  {title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
