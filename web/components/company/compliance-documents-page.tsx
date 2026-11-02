"use client";

import { FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { StatusChip } from "@/components/ui/status-chip";
import { TextArea } from "@/components/ui/text-area";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { expiryText, STATUS_TONE } from "@/lib/company/compliance";

import { FormSheet } from "./form-sheet";

type Slot = components["schemas"]["DocumentSlot"];

/** `/company/compliance-documents` (plan 8.15): the 18 documents a sponsor is expected to hold. */
export function ComplianceDocumentsPage({
  slots,
  filled,
  total,
}: {
  slots: Slot[];
  filled: number;
  total: number;
}) {
  const can = useCan();
  const mayEdit = can("document.file.write");
  const [editing, setEditing] = useState<Slot | null>(null);

  return (
    <>
      <PageHeader
        title="Compliance documents"
        description={`${filled} of ${total} held. Add an expiry date and we will remind you before it runs out.`}
      />
      <GroupedList heading="Documents">
        {slots.map((slot) => (
          <GroupedRow
            key={slot.doc_type}
            title={slot.label}
            icon={<Icon icon={FileText} />}
            detail={
              <StatusChip tone={STATUS_TONE[slot.status]}>
                {slot.status === "missing"
                  ? "Missing"
                  : expiryText(slot.status, slot.record?.expires_on ?? null)}
              </StatusChip>
            }
            {...(mayEdit ? { onClick: () => setEditing(slot) } : {})}
          />
        ))}
      </GroupedList>
      {editing ? (
        <DocumentSheet key={editing.doc_type} slot={editing} onClose={() => setEditing(null)} />
      ) : null}
    </>
  );
}

function DocumentSheet({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const record = slot.record;
  const [expires, setExpires] = useState<string | null>(record?.expires_on ?? null);
  const [notes, setNotes] = useState(record?.notes ?? "");
  const [pending, setPending] = useState<File | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [fileProblem, setFileProblem] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setFileProblem(undefined);
    if (!record && !pending) {
      setFileProblem("Choose the document to add.");
      return;
    }
    setBusy(true);
    let outcome;
    if (pending) {
      const body = new FormData();
      body.append("file", pending);
      body.append("doc_type", slot.doc_type);
      if (expires) body.append("expires_on", expires);
      if (notes.trim()) body.append("notes", notes.trim());
      outcome = await attempt((client) =>
        client.POST("/compliance-documents", {
          body: { file: "", doc_type: slot.doc_type },
          bodySerializer: () => body,
        }),
      );
    } else if (record) {
      outcome = await attempt((client) =>
        client.PATCH("/compliance-documents/{document_id}", {
          params: { path: { document_id: record.id } },
          body: { expires_on: expires, notes: notes.trim() || null },
        }),
      );
    }
    setBusy(false);
    if (outcome?.ok) {
      toast.show({ title: "Document saved", tone: "success" });
      router.refresh();
      onClose();
    } else if (outcome) {
      if (pending) setFileProblem(outcome.problem.message);
      else setProblem(outcome.problem);
    }
  }

  async function view() {
    if (!record) return;
    const outcome = await attempt((client) =>
      client.GET("/compliance-documents/{document_id}/file", {
        params: { path: { document_id: record.id } },
      }),
    );
    if (!outcome.ok) {
      setProblem(outcome.problem);
      return;
    }
    const link = document.createElement("a");
    link.href = outcome.data.url;
    link.rel = "noreferrer";
    link.click();
  }

  async function remove() {
    if (!record) return;
    const outcome = await attempt((client) =>
      client.DELETE("/compliance-documents/{document_id}", {
        params: { path: { document_id: record.id } },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: "Document removed", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  const items: UploadItem[] = pending
    ? [
        {
          id: pending.name,
          name: pending.name,
          size: pending.size,
          status: fileProblem ? "rejected" : "safe",
          ...(fileProblem ? { message: fileProblem } : {}),
        },
      ]
    : [];

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={slot.label}
      description={record ? "A new upload replaces the current document." : "Not added yet."}
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(record
        ? {
            archive: {
              label: "Remove",
              question: "Remove this document?",
              detail: "It stops counting as held. The file is kept in your records.",
              onConfirm: remove,
            },
          }
        : {})}
    >
      {record ? (
        <div className="bg-fill-secondary rounded-control flex flex-wrap items-center justify-between gap-2 p-3">
          <div className="min-w-0">
            <p className="text-callout text-label truncate">{record.file_name}</p>
            <p className="text-footnote text-label-secondary">
              {expiryText(record.status, record.expires_on)}
            </p>
          </div>
          <Button variant="gray" size="sm" onClick={() => void view()}>
            View
          </Button>
        </div>
      ) : null}
      <FileDrop
        label={record ? "Replace the document" : "Add the document"}
        description="A PDF, Word file, JPG or PNG up to 25 MB. It is checked for viruses when you save."
        accept={[
          "application/pdf",
          "image/jpeg",
          "image/png",
          "application/msword",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]}
        maxBytes={25 * 1024 * 1024}
        items={items}
        onFiles={(files) => {
          setPending(files[0] ?? null);
          setFileProblem(undefined);
        }}
        onRemove={() => setPending(null)}
      />
      {!pending && fileProblem ? <Alert tone="danger" title={fileProblem} /> : null}
      <DatePicker
        label="Expiry date (optional)"
        name="expires_on"
        value={expires}
        onChange={setExpires}
        hint="Leave empty if it does not run out."
      />
      <TextArea
        label="Notes (optional)"
        name="notes"
        rows={3}
        maxLength={1000}
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
      />
    </FormSheet>
  );
}
