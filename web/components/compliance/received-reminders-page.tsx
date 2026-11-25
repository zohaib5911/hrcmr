"use client";

import { FileText } from "lucide-react";
import { useEffect } from "react";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import type { components } from "@/lib/api/schema";
import { sentTime } from "@/lib/compliance/reminders";
import { shortDate } from "@/lib/employees/profile";
import { cn } from "@/lib/utils";

type Received = components["schemas"]["ReceivedReminder"];

export function ReceivedRemindersPage({
  reminders,
  selectedId,
}: {
  /** `null` when the person may not read reminders (ISS-13): only the header is shown. */
  reminders: Received[] | null;
  selectedId?: string;
}) {
  useEffect(() => {
    if (selectedId) {
      const item = document.getElementById("reminder-" + selectedId);
      item?.focus({ preventScroll: true });
      item?.scrollIntoView({ block: "start" });
    }
  }, [selectedId]);
  return (
    <>
      <PageHeader
        title="My documents"
        description={
          reminders
            ? "Reminders and messages from HR."
            : "Policies HR asks you to read and confirm."
        }
      />
      {reminders === null ? null : (
        <section aria-label="Reminders from HR" className="flex flex-col gap-4">
          <h2 className="text-headline text-label">Reminders from HR</h2>
          {reminders.length ? (
            reminders.map((item) => (
              <article
                key={item.id}
                id={"reminder-" + item.id}
                tabIndex={-1}
                aria-label={item.title}
                className={cn(
                  "bg-elevated rounded-card shadow-e1 p-5 flex flex-col gap-3 outline-none focus-visible:ring-accent focus-visible:ring-2 scroll-mt-24",
                  selectedId === item.id && "ring-accent ring-2",
                )}
              >
                <h3 className="text-headline text-label">{item.title}</h3>
                <p className="text-caption text-label-secondary">
                  From {item.sender_name} · {sentTime(item.sent_at)}
                </p>
                <p className="text-body text-label whitespace-pre-wrap break-words">
                  {item.message}
                </p>
                <p className="text-callout text-label-secondary">
                  Expiry / follow-up {shortDate(item.expires_on)}
                </p>
              </article>
            ))
          ) : (
            <EmptyState
              icon={FileText}
              title="No reminders yet"
              description="When HR sends you a reminder, its message and next steps will appear here."
            />
          )}
        </section>
      )}
    </>
  );
}
