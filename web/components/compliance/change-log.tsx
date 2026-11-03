"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useCan } from "@/components/app/session-context";
import {
  EmployeeChangeSheet,
  ReportedSheet,
  ReportingSources,
} from "@/components/compliance/change-forms";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { attempt, type Problem } from "@/lib/auth/request";
import { changeLabel, STATUS, type Change, type Reporting } from "@/lib/compliance/changes";
import { documentLabel } from "@/lib/compliance/sponsor-documents";
import { shortDate } from "@/lib/employees/profile";

export function ChangeSummary({ record }: { record: Reporting }) {
  const status = STATUS[record.status];
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-headline text-label">{changeLabel(record)}</h3>
        <StatusChip tone={status.tone}>{status.label}</StatusChip>
      </div>
      <p className="text-callout text-label-secondary">
        {"employee_id" in record ? "Event" : "Became aware"} {shortDate(record.change_date)}
        {record.deadline_date
          ? " · Deadline " + shortDate(record.deadline_date)
          : " · Report promptly"}
      </p>
      {record.status === "unreported" && record.working_days_left !== null && (
        <p className="text-callout text-label">
          {record.working_days_left === 0
            ? "Due today"
            : record.working_days_left +
              " working " +
              (record.working_days_left === 1 ? "day" : "days") +
              " left"}
        </p>
      )}
      {record.reported_date && (
        <p className="text-callout text-label">
          Reported by {record.reporter_name ?? "recorded user"} on {shortDate(record.reported_date)}{" "}
          · {record.reported_reference}
        </p>
      )}
      {record.reported_on_time === false && (
        <Alert tone="warning" title="Reported after the deadline" />
      )}
      {record.remarks && <p className="text-body text-label break-words">{record.remarks}</p>}
      {"employee_id" in record && (
        <details>
          <summary className="text-callout text-tint cursor-pointer">
            Snapshot and documents
          </summary>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {[
              ["Employment type", record.employment_type?.replaceAll("_", " ") ?? "Not set"],
              ["Job title", record.job_title ?? "Not set"],
              ["Nationality", record.nationality ?? "Not set"],
              ["Contact number", record.contact_number ?? "Not set"],
              ["Address", record.address ?? "Not set"],
              ["Employee told to inform HR", record.ack_inform_hr ? "Yes" : "No"],
              [
                "Employee told to cooperate with interview",
                record.ack_home_office_interview ? "Yes" : "No",
              ],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-caption text-label-secondary">{label}</dt>
                <dd className="text-body text-label break-words">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-caption text-label-secondary mt-3">
            Documents kept with this snapshot
          </p>
          {record.documents.length > 0 ? (
            <ul className="text-callout text-label mt-1">
              {record.documents.map((d) => (
                <li key={d.id}>
                  {documentLabel(d.doc_type)} · version {d.version}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-callout text-label-secondary mt-1">No documents selected.</p>
          )}
        </details>
      )}
    </div>
  );
}

export function EmployeeChanges({ id }: { id: string }) {
  const can = useCan();
  const [records, setRecords] = useState<Change[] | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [sheet, setSheet] = useState<"new" | Change | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/employees/{employee_id}/changes", { params: { path: { employee_id: id } } }),
      );
      if (!active) return;
      if (result.ok) {
        setRecords(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [id, refresh]);
  return (
    <section aria-label="Change of circumstances" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-headline text-label">Change of circumstances</h2>
        {can("employee.change_of_circumstances.write") && (
          <Button size="sm" onClick={() => setSheet("new")}>
            Log a change
          </Button>
        )}
      </div>
      {problem && <Alert tone="danger" title={problem.message} />}
      {!records && !problem && (
        <p role="status" className="text-callout text-label-secondary">
          Loading changes…
        </p>
      )}
      {records?.length === 0 && (
        <p className="text-body text-label-secondary">No changes logged.</p>
      )}
      {records?.map((record) => (
        <article
          key={record.id}
          className="bg-elevated rounded-card shadow-e1 p-4 flex flex-col gap-4"
        >
          <ChangeSummary record={record} />
          {!record.reported_at && can("employee.change_of_circumstances.write") && (
            <div>
              <Button variant="gray" size="sm" onClick={() => setSheet(record)}>
                Mark as reported
              </Button>
            </div>
          )}
        </article>
      ))}
      <Link
        href="/sponsor-compliance/change-of-circumstances"
        className="text-callout text-tint underline"
      >
        View company-wide changes
      </Link>
      <ReportingSources />
      {sheet === "new" ? (
        <EmployeeChangeSheet
          employeeId={id}
          onClose={() => setSheet(null)}
          onSaved={() => setRefresh((v) => v + 1)}
        />
      ) : (
        sheet && (
          <ReportedSheet
            record={sheet}
            onClose={() => setSheet(null)}
            onSaved={() => setRefresh((v) => v + 1)}
          />
        )
      )}
    </section>
  );
}
