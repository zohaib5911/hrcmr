"use client";

import { BellRing } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { ReminderReview } from "@/components/compliance/reminder-review";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { StatusChip } from "@/components/ui/status-chip";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  REGISTER_TYPES,
  REMINDER_STATUS,
  EMAIL_STATUS,
  sentTime,
  type Reminder,
  type ReminderSlot,
  type RegisterType,
} from "@/lib/compliance/reminders";
import { shortDate } from "@/lib/employees/profile";

const HISTORY_COLUMNS: Column<Reminder>[] = [
  {
    id: "employee",
    header: "Employee",
    primary: true,
    sortValue: (r) => r.employee_name.toLowerCase(),
    cell: (r) => (
      <div>
        <p className="text-body text-label">{r.employee_name}</p>
        <p className="text-footnote text-label-secondary">{r.employee_number}</p>
      </div>
    ),
  },
  {
    id: "document",
    header: "Document / check",
    sortValue: (r) => r.document_label,
    cell: (r) => r.document_label,
  },
  {
    id: "threshold",
    header: "Threshold",
    sortValue: (r) => r.threshold_days,
    cell: (r) => r.threshold_days + " days",
  },
  {
    id: "sender",
    header: "Sent by",
    sortValue: (r) => r.sender_name,
    cell: (r) => r.sender_name ?? "HR",
  },
  {
    id: "sent",
    header: "When",
    sortValue: (r) => r.sent_at,
    cell: (r) => (r.sent_at ? sentTime(r.sent_at) : "Not sent"),
  },
  {
    id: "email",
    header: "Email nudge",
    sortValue: (r) => r.email_status,
    cell: (r) => (r.email_status ? EMAIL_STATUS[r.email_status] : "Not queued"),
  },
];

export function RemindersPage({
  register,
  due,
  history,
  initialReminderId,
}: {
  register: ReminderSlot[];
  due: Reminder[];
  history: Reminder[];
  initialReminderId?: string;
}) {
  const router = useRouter();
  const can = useCan();
  const [tab, setTab] = useState("due");
  const [kind, setKind] = useState<RegisterType>("visa");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(initialReminderId ?? null);
  const records = new Map(
    [...register.flatMap((slot) => slot.reminders), ...due, ...history].map((r) => [r.id, r]),
  );
  const words = search.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (row: {
    employee_name: string;
    employee_number: string;
    document_label: string;
  }) =>
    words.every((w) =>
      (row.employee_name + " " + row.employee_number + " " + row.document_label)
        .toLowerCase()
        .includes(w),
    );
  const dueRows = due.filter(matches);
  const slots = register.filter(
    (row) =>
      matches(row) &&
      (kind === "other" ? ["other", "national_id"].includes(row.doc_type) : row.doc_type === kind),
  );
  const historyRows = history.filter(matches);
  const record = selected ? records.get(selected) : null;
  const columns: Column<ReminderSlot>[] = [
    {
      id: "employee",
      header: "Employee",
      primary: true,
      sortValue: (r) => r.employee_name.toLowerCase(),
      cell: (r) => (
        <div>
          <p className="text-body text-label">{r.employee_name}</p>
          <p className="text-footnote text-label-secondary">{r.employee_number}</p>
        </div>
      ),
    },
    {
      id: "document",
      header: "Document / check",
      sortValue: (r) => r.document_label,
      cell: (r) => r.document_label,
    },
    {
      id: "expiry",
      header: "Expiry / follow-up",
      sortValue: (r) => r.expires_on,
      cell: (r) => (r.expires_on ? shortDate(r.expires_on) : "No expiry recorded"),
    },
    {
      id: "thresholds",
      header: "Thresholds",
      exportValue: (r) =>
        r.reminders
          .map((item) => item.threshold_days + ": " + REMINDER_STATUS[item.status].label)
          .join("; "),
      cell: (r) => (
        <div className="flex flex-wrap gap-2 justify-end sm:justify-start">
          {r.reminders.length ? (
            r.reminders.map((item) => (
              <Button
                key={item.id}
                size="sm"
                variant="gray"
                onDoubleClick={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelected(item.id);
                }}
              >
                {item.threshold_days} days · {REMINDER_STATUS[item.status].label}
              </Button>
            ))
          ) : (
            <span className="text-label-secondary">No expiry reminders</span>
          )}
        </div>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Compliance reminders"
        description="Review expiry and follow-up reminders before they go to employees."
      />
      <div className="flex flex-col gap-4">
        <SearchField
          label="Search reminders"
          listSearch
          containerClassName="sm:w-80"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Tabs value={tab} onValueChange={setTab}>
          <div className="max-w-full overflow-x-auto">
            <TabsList aria-label="Reminder views">
              <TabsTrigger value="due">Due now ({due.length})</TabsTrigger>
              <TabsTrigger value="register">Document register</TabsTrigger>
              <TabsTrigger value="history">History ({history.length})</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="due" className="pt-4">
            <div className="flex flex-col gap-3">
              {dueRows.length ? (
                dueRows.map((row) => (
                  <article
                    key={row.id}
                    aria-label={row.employee_name + " · " + row.document_label}
                    className="bg-elevated rounded-card shadow-e1 p-4 flex flex-wrap items-start justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <h2 className="text-headline text-label break-words">{row.employee_name}</h2>
                      <p className="text-callout text-label-secondary">
                        {row.document_label} · {row.threshold_days}-day threshold
                      </p>
                      <p className="text-caption text-label-secondary">
                        Expiry / follow-up {shortDate(row.expires_on)}
                      </p>
                      <div className="mt-2">
                        <StatusChip tone="warning">Due</StatusChip>
                      </div>
                    </div>
                    <Button size="sm" onClick={() => setSelected(row.id)}>
                      {can("compliance.reminder.send") ? "Review & send" : "View reminder"}
                    </Button>
                  </article>
                ))
              ) : (
                <EmptyState
                  icon={BellRing}
                  title={search.trim() ? "No reminders match" : "No reminders due"}
                  description={
                    search.trim()
                      ? "Try a different search."
                      : "Due expiry and follow-up reminders will appear here for review."
                  }
                />
              )}
            </div>
          </TabsContent>
          <TabsContent value="register" className="pt-4">
            <Tabs value={kind} onValueChange={(v) => setKind(v as RegisterType)}>
              <div className="max-w-full overflow-x-auto">
                <TabsList aria-label="Document type">
                  {REGISTER_TYPES.map((type) => (
                    <TabsTrigger key={type.value} value={type.value}>
                      {type.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </div>
              <TabsContent value={kind} className="pt-4">
                <DataTable
                  caption="Reminder document register"
                  columns={columns}
                  rows={slots}
                  getRowId={(row) => row.kind + ":" + row.source_id}
                  onRowOpen={(row) => {
                    const next =
                      row.reminders.find((item) => item.status === "due") ?? row.reminders[0];
                    if (next) setSelected(next.id);
                  }}
                  defaultSort={{ column: "employee", direction: "asc" }}
                  empty={
                    <EmptyState
                      icon={BellRing}
                      title="No matching documents"
                      description="Current documents and check follow-ups will appear under their type."
                    />
                  }
                />
              </TabsContent>
            </Tabs>
          </TabsContent>
          <TabsContent value="history" className="pt-4">
            <DataTable
              caption="Sent reminder history"
              columns={HISTORY_COLUMNS}
              rows={historyRows}
              getRowId={(row) => row.id}
              onRowOpen={(row) => setSelected(row.id)}
              defaultSort={{ column: "sent", direction: "desc" }}
              empty={
                <EmptyState
                  icon={BellRing}
                  title="No reminders sent"
                  description="Sent messages are kept here with the person who sent them and the time."
                />
              }
            />
          </TabsContent>
        </Tabs>
      </div>
      {record && (
        <ReminderReview
          key={record.id}
          initial={record}
          onClose={() => setSelected(null)}
          onChanged={() => router.refresh()}
        />
      )}
    </>
  );
}
