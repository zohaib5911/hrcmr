"use client";

import { useEffect, useState, type FormEvent } from "react";

import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FileDrop } from "@/components/ui/file-drop";
import { RadioCards } from "@/components/ui/radio-cards";
import { Select } from "@/components/ui/select";
import { Stepper } from "@/components/ui/stepper";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatBytes } from "@/lib/ui/files";

import {
  AUDIENCE_LABELS,
  CATEGORY_LABELS,
  MODE_LABELS,
  type AudienceType,
  type ConfirmationMode,
  type PolicyCategory,
  type PolicyOut,
  type PolicyRecipient,
} from "./labels";

type Draft = components["schemas"]["PolicyDraft"];
type Lookup = { id: string; label: string };

const STEPS = [
  { id: "details", label: "Details" },
  { id: "file", label: "Upload file" },
  { id: "send", label: "Recipients & send" },
] as const;
const NEEDS_IDS: readonly AudienceType[] = ["departments", "locations", "named"];
const SCAN_FAILED = ["infected", "error"];

function fieldProblem(field: string, message: string): Problem {
  return { code: "VALIDATION_ERROR", message, field } as Problem;
}

/**
 * The "New document" sheet: details, then the file, then who receives it. A draft is saved at the
 * first step, so closing the sheet keeps it; the list shows drafts until they are sent.
 */
export function NewDocumentSheet({
  existing,
  onOpenChange,
  onSaved,
}: {
  existing: PolicyOut | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (policy: PolicyOut) => void;
}) {
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<PolicyOut | null>(existing);
  const [title, setTitle] = useState(existing?.title ?? "");
  const [category, setCategory] = useState<PolicyCategory>(existing?.category ?? "company_policy");
  const [mode, setMode] = useState<ConfirmationMode>(existing?.confirmation_mode ?? "accept");
  const [audience, setAudience] = useState<AudienceType>(existing?.audience_type ?? "everyone");
  const [ids, setIds] = useState<string[]>(existing?.audience_ids ?? []);
  const [days, setDays] = useState(String(existing?.accept_within_days ?? 14));
  const [autoStarters, setAutoStarters] = useState(existing?.auto_send_new_starters ?? false);
  const [picked, setPicked] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ items: PolicyRecipient[]; token: string } | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  // A file that is still being checked for viruses: look again every two seconds.
  useEffect(() => {
    if (!draft || draft.scan_status !== "pending") return;
    const timer = window.setTimeout(() => {
      void attempt((c) =>
        c.GET("/policies/{policy_id}", { params: { path: { policy_id: draft.id } } }),
      ).then((result) => {
        if (result.ok) setDraft(result.data);
      });
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [draft]);

  // Who will receive it, as the server works it out now. Sending checks this same list again.
  useEffect(() => {
    if (step !== 2 || !draft) return;
    let active = true;
    void attempt((c) =>
      c.GET("/policies/{policy_id}/recipients", { params: { path: { policy_id: draft.id } } }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setPreview({ items: result.data.items, token: result.data.preview_token });
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [step, draft, refresh]);

  async function saveDetails(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!title.trim()) return setProblem(fieldProblem("title", "Enter a title for this document."));
    if (NEEDS_IDS.includes(audience) && ids.length === 0)
      return setProblem(
        fieldProblem("audience_ids", "Choose at least one item for this audience."),
      );
    const within = Number(days);
    if (!Number.isInteger(within) || within < 1 || within > 365)
      return setProblem(fieldProblem("accept_within_days", "Enter a whole number from 1 to 365."));
    const body: Draft = {
      title: title.trim(),
      category,
      confirmation_mode: mode,
      audience_type: audience,
      audience_ids: NEEDS_IDS.includes(audience) ? ids : [],
      accept_within_days: within,
      auto_send_new_starters: autoStarters,
    };
    setBusy(true);
    const result = await attempt((c) =>
      draft
        ? c.PATCH("/policies/{policy_id}", { params: { path: { policy_id: draft.id } }, body })
        : c.POST("/policies", { body }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    setDraft(result.data);
    setStep(1);
  }

  async function upload(files: File[]) {
    const file = files[0];
    if (!file || !draft) return;
    setProblem(null);
    setBusy(true);
    setPicked(file);
    const form = new FormData();
    form.append("file", file);
    const result = await attempt((c) =>
      c.POST("/policies/{policy_id}/file", {
        params: { path: { policy_id: draft.id } },
        body: { file: "" },
        bodySerializer: () => form,
      }),
    );
    setBusy(false);
    if (result.ok) setDraft(result.data);
    else setProblem(result.problem);
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!draft || !preview) return;
    setProblem(null);
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/policies/{policy_id}/send", {
        params: { path: { policy_id: draft.id } },
        body: { preview_token: preview.token },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Policy sent", tone: "success" });
      onSaved(result.data);
      return;
    }
    setProblem(result.problem);
    if (result.problem.code === "POLICY_PREVIEW_CHANGED") {
      setPreview(null);
      setRefresh((n) => n + 1);
    }
  }

  const scan = draft?.scan_status ?? null;
  const fileReady = scan === "clean";
  const people = preview?.items.length ?? 0;
  const saveLabel =
    step === 0
      ? "Continue"
      : step === 1
        ? "Continue"
        : people > 0
          ? `Send to ${people} ${people === 1 ? "person" : "people"}`
          : "Send";

  return (
    <FormSheet
      open
      title={existing ? "Continue policy" : "New document"}
      description="Details, then the file, then who receives it."
      onOpenChange={onOpenChange}
      onSubmit={(event) => {
        if (step === 0) void saveDetails(event);
        else if (step === 1) {
          event.preventDefault();
          if (fileReady) setStep(2);
          else
            setProblem({
              code: "VALIDATION_ERROR",
              message: "Wait for the file to pass its check, then continue.",
            } as Problem);
        } else void send(event);
      }}
      busy={busy}
      problem={problem}
      saveLabel={saveLabel}
    >
      <fieldset disabled={busy} className="flex min-w-0 flex-col gap-4">
        <Stepper steps={STEPS} current={step} />

        {step === 0 && (
          <>
            <TextField
              label="Title"
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              error={problem?.field === "title" ? problem.message : undefined}
            />
            <Select
              label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value as PolicyCategory)}
            >
              {(Object.keys(CATEGORY_LABELS) as PolicyCategory[]).map((value) => (
                <option key={value} value={value}>
                  {CATEGORY_LABELS[value]}
                </option>
              ))}
            </Select>
            <RadioCards
              legend="How people confirm"
              value={mode}
              onValueChange={(value) => setMode(value as ConfirmationMode)}
              options={(Object.keys(MODE_LABELS) as ConfirmationMode[]).map((value) => ({
                value,
                title: MODE_LABELS[value],
                description:
                  value === "accept"
                    ? "A tick box: I have read and accept."
                    : "They type their full name as a signature.",
              }))}
            />
            <Select
              label="Who receives it"
              value={audience}
              onChange={(e) => {
                setAudience(e.target.value as AudienceType);
                setIds([]);
              }}
            >
              {(Object.keys(AUDIENCE_LABELS) as AudienceType[]).map((value) => (
                <option key={value} value={value}>
                  {AUDIENCE_LABELS[value]}
                </option>
              ))}
            </Select>
            {NEEDS_IDS.includes(audience) && (
              <AudiencePicker
                type={audience}
                ids={ids}
                onChange={setIds}
                error={problem?.field === "audience_ids" ? problem.message : undefined}
              />
            )}
            <TextField
              label="Accept within (days)"
              type="number"
              min={1}
              max={365}
              required
              value={days}
              onChange={(e) => setDays(e.target.value)}
              error={problem?.field === "accept_within_days" ? problem.message : undefined}
            />
            <Checkbox
              label="Send to new starters automatically"
              description="People who join later, and who are in this audience, get it too."
              checked={autoStarters}
              onCheckedChange={(value) => setAutoStarters(value === true)}
            />
          </>
        )}

        {step === 1 && (
          <>
            {draft?.file_id ? (
              <div className="border-separator flex flex-col gap-2 rounded-xl border p-4">
                <p className="text-body break-all">{draft.file_name}</p>
                <p className="text-footnote text-label-secondary">
                  {picked ? formatBytes(picked.size) : null}
                </p>
                {scan === "pending" && (
                  <StatusChip tone="info">Checking the file for viruses…</StatusChip>
                )}
                {fileReady && <StatusChip tone="success">Checked and ready</StatusChip>}
                {scan && SCAN_FAILED.includes(scan) && (
                  <Alert tone="danger" title="This file could not be used. Upload another file." />
                )}
              </div>
            ) : null}
            <FileDrop
              label={draft?.file_id ? "Replace the file" : "Policy file"}
              description="PDF, JPG, PNG or Word, up to 25 MB. Everyone reads the file you upload here."
              accept={[".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]}
              maxBytes={25 * 1024 * 1024}
              items={
                busy && picked
                  ? [{ id: picked.name, name: picked.name, size: picked.size, status: "uploading" }]
                  : []
              }
              onFiles={(files) => void upload(files)}
              disabled={busy}
            />
          </>
        )}

        {step === 2 && (
          <>
            {preview && people === 0 && (
              <Alert
                tone="danger"
                title="No one matches this audience yet. Go back and change who receives it."
              />
            )}
            {preview && people > 0 && (
              <>
                <p className="text-callout text-label-secondary">
                  {people} {people === 1 ? "person" : "people"} will receive this. Each has{" "}
                  {draft?.accept_within_days} days to{" "}
                  {draft?.confirmation_mode === "sign" ? "sign" : "accept"}.
                </p>
                <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto">
                  {preview.items.slice(0, 200).map((person) => (
                    <li
                      key={person.employee_id}
                      className="text-callout flex justify-between gap-3"
                    >
                      <span className="min-w-0 break-words">
                        {person.employee_name}{" "}
                        <span className="text-label-secondary">#{person.employee_number}</span>
                      </span>
                      <span className="text-label-secondary shrink-0">Due {person.due_on}</span>
                    </li>
                  ))}
                </ul>
                {people > 200 && (
                  <p className="text-footnote text-label-secondary">And {people - 200} more.</p>
                )}
              </>
            )}
          </>
        )}

        {step > 0 && (
          <div>
            <Button
              type="button"
              variant="plain"
              size="sm"
              onClick={() => setStep((n) => Math.max(0, n - 1))}
            >
              Back
            </Button>
          </div>
        )}
      </fieldset>
    </FormSheet>
  );
}

/** Departments, locations or named people, picked from the company's own lists. */
function AudiencePicker({
  type,
  ids,
  onChange,
  error,
}: {
  type: AudienceType;
  ids: string[];
  onChange: (ids: string[]) => void;
  error?: string | undefined;
}) {
  const [options, setOptions] = useState<Lookup[]>([]);
  const [search, setSearch] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      if (type === "departments") {
        const result = await attempt((c) => c.GET("/departments"));
        return result.ok ? result.data.map((row) => ({ id: row.id, label: row.name })) : null;
      }
      if (type === "locations") {
        const result = await attempt((c) => c.GET("/locations"));
        return result.ok ? result.data.map((row) => ({ id: row.id, label: row.name })) : null;
      }
      const result = await attempt((c) =>
        c.GET("/employees", { params: { query: { q: search.trim() || undefined } } }),
      );
      return result.ok
        ? result.data.employees.map((row) => ({
            id: row.id,
            label: `${row.first_name} ${row.last_name} (#${row.employee_number})`,
          }))
        : null;
    };
    void load().then((rows) => {
      if (!active) return;
      setFailed(rows === null);
      setOptions(rows ?? []);
    });
    return () => {
      active = false;
    };
  }, [type, search]);

  const toggle = (id: string, on: boolean) =>
    onChange(on ? [...ids, id] : ids.filter((item) => item !== id));

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-callout text-label mb-1 font-medium">
        {type === "departments" ? "Departments" : type === "locations" ? "Locations" : "People"}
      </legend>
      {type === "named" && (
        <TextField
          label="Search people"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          maxLength={100}
        />
      )}
      {failed && <Alert tone="danger" title="These choices could not be loaded. Try again." />}
      {!failed && options.length === 0 && (
        <p className="text-callout text-label-secondary">Nothing to choose from yet.</p>
      )}
      <div className="flex max-h-56 flex-col gap-2 overflow-y-auto">
        {options.map((option) => (
          <Checkbox
            key={option.id}
            label={option.label}
            checked={ids.includes(option.id)}
            onCheckedChange={(value) => toggle(option.id, value === true)}
          />
        ))}
      </div>
      {error && <p className="text-footnote text-danger">{error}</p>}
    </fieldset>
  );
}
