"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useCan, useMe } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { StatusChip } from "@/components/ui/status-chip";
import { TextArea } from "@/components/ui/text-area";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";
import { REMINDER_STATUS, EMAIL_STATUS, sentTime, type Reminder } from "@/lib/compliance/reminders";
import { shortDate } from "@/lib/employees/profile";

type Action = "draft" | "snooze" | "send" | "wording";

export function ReminderReview({
  initial,
  onClose,
  onChanged,
}: {
  initial: Reminder;
  onClose: () => void;
  onChanged: () => void;
}) {
  const maySend = useCan()("compliance.reminder.send");
  const aiAvailable = useMe()?.ai_available ?? false;
  const toast = useToast();
  const [record, setRecord] = useState(initial);
  const [message, setMessage] = useState(initial.message_draft);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState<Action | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<string>();
  const [wording, setWording] = useState<"ai" | "template" | null>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const result = await attempt((c) =>
        c.GET("/reminders/{reminder_id}", { params: { path: { reminder_id: initial.id } } }),
      );
      if (!active) return;
      if (result.ok) {
        setRecord(result.data);
        setMessage(result.data.message_draft);
        setLoaded(true);
      } else setProblem(result.problem);
    }
    void load();
    return () => {
      active = false;
    };
  }, [initial.id]);
  const editable = maySend && !["sent", "cancelled"].includes(record.status);
  async function act(action: Action) {
    setError(undefined);
    setProblem(null);
    if (!message.trim()) return setError("Write a message for the employee.");
    setBusy(action);
    const request = {
      params: { path: { reminder_id: record.id } },
      body: { message: message.trim() },
    };
    const result = await attempt((c) =>
      action === "draft"
        ? c.PATCH("/reminders/{reminder_id}", request)
        : action === "snooze"
          ? c.POST("/reminders/{reminder_id}/snooze", request)
          : c.POST("/reminders/{reminder_id}/send", request),
    );
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    setRecord(result.data);
    setMessage(result.data.message_draft);
    toast.show({
      title:
        action === "send"
          ? "Reminder sent; email nudge queued"
          : action === "snooze"
            ? "Reminder snoozed for 7 days"
            : "Draft saved",
      tone: "success",
    });
    onChanged();
    if (action !== "draft") onClose();
  }
  /** Replaces the message with a suggestion. Nothing is saved until HR saves or sends it. */
  async function draftWording() {
    setError(undefined);
    setProblem(null);
    setBusy("wording");
    const result = await attempt((c) =>
      c.POST("/reminders/{reminder_id}/wording", {
        params: { path: { reminder_id: record.id } },
      }),
    );
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    setMessage(result.data.message);
    setWording(result.data.source);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (record.can_send && editable && loaded && !busy) void act("send");
  }
  const status = REMINDER_STATUS[record.status];
  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        title="Review reminder"
        description={record.employee_name + " · " + record.document_label}
        readOnly={!editable}
        footer={
          <div className="flex w-full flex-wrap justify-end gap-2">
            <Button variant="gray" onClick={onClose}>
              Close review
            </Button>
            {editable && (
              <>
                <Button
                  variant="gray"
                  disabled={!loaded || !!busy}
                  loading={busy === "draft"}
                  onClick={() => void act("draft")}
                >
                  Save draft
                </Button>
                {["due", "snoozed"].includes(record.status) && (
                  <Button
                    variant="plain"
                    disabled={!loaded || !!busy}
                    loading={busy === "snooze"}
                    onClick={() => void act("snooze")}
                  >
                    Not now (7 days)
                  </Button>
                )}
                <Button
                  type="submit"
                  form="reminder-review"
                  disabled={!loaded || !!busy || !record.can_send}
                  loading={busy === "send"}
                >
                  Send reminder
                </Button>
              </>
            )}
          </div>
        }
      >
        <form id="reminder-review" onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2 items-center">
            <StatusChip tone={status.tone}>{status.label}</StatusChip>
            {!["sent", "cancelled"].includes(record.status) && (
              <span className="text-caption text-label-secondary">Drafted, not sent</span>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-caption text-label-secondary">Expiry / follow-up</dt>
              <dd className="text-callout text-label">{shortDate(record.expires_on)}</dd>
            </div>
            <div>
              <dt className="text-caption text-label-secondary">Threshold</dt>
              <dd className="text-callout text-label">
                {record.threshold_days} days · {shortDate(record.due_on)}
              </dd>
            </div>
          </dl>
          {!loaded && !problem && (
            <p role="status" className="text-callout text-label-secondary">
              Loading reminder…
            </p>
          )}
          {record.sent_at && (
            <p className="text-callout text-label">
              Sent by {record.sender_name ?? "HR"} on {sentTime(record.sent_at)}
              {record.email_status ? " · " + EMAIL_STATUS[record.email_status] : ""}
            </p>
          )}
          {record.snoozed_until && (
            <p className="text-callout text-label-secondary">
              Snoozed until {sentTime(record.snoozed_until)}.
            </p>
          )}
          {record.cancel_reason && <Alert tone="info" title={record.cancel_reason} />}
          {editable && !record.recipient_available && (
            <Alert tone="warning" title="Employee account not linked">
              Link an active, verified employee account in{" "}
              <Link className="text-tint underline" href="/company/users">
                User access
              </Link>{" "}
              before sending.
            </Alert>
          )}
          {problem && <Alert tone="danger" title={problem.message} />}
          {editable ? (
            <div className="flex flex-col gap-2">
              {aiAvailable && (
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="gray"
                    disabled={!loaded || !!busy}
                    loading={busy === "wording"}
                    onClick={() => void draftWording()}
                  >
                    Draft with AI
                  </Button>
                  {wording === "ai" && (
                    <span className="text-caption text-label-secondary">
                      AI wording. Check it before you send.
                    </span>
                  )}
                  {wording === "template" && (
                    <span className="text-caption text-label-secondary">
                      AI wording is not available right now, so the standard message is shown.
                    </span>
                  )}
                </div>
              )}
              <TextArea
                label="Message for employee"
                name="message"
                rows={8}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={2000}
                disabled={!loaded || !!busy}
              />
            </div>
          ) : (
            <div>
              <h3 className="text-callout text-label mb-2">Message for employee</h3>
              <p className="text-body text-label whitespace-pre-wrap break-words">
                {record.message_draft}
              </p>
            </div>
          )}
          {editable && (
            <p className="text-caption text-label-secondary">
              This message appears in My documents. The email only says a reminder is waiting and
              links to the signed-in app.
            </p>
          )}
          {error && <Alert tone="danger" title={error} />}
        </form>
      </SheetContent>
    </Sheet>
  );
}
