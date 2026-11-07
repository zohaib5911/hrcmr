"use client";

import { useState, type FormEvent } from "react";

import { FormSheet } from "@/components/company/form-sheet";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { downloadBlob } from "@/lib/attendance";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type Draft = components["schemas"]["LetterDraftOut"];
type LetterType = Draft["letter_type"];
type Tone = Draft["tone"];

const MAX_POINTS = 10;
const LETTER_TYPES: { value: LetterType; label: string }[] = [
  { value: "offer", label: "Offer letter" },
  { value: "welcome", label: "Welcome or onboarding letter" },
  { value: "disciplinary", label: "Disciplinary letter" },
  { value: "written_warning", label: "Formal written warning" },
  { value: "policy_explainer", label: "Policy explainer" },
  { value: "reference", label: "Employment reference" },
  { value: "termination", label: "Termination letter" },
];
const TONES: { value: Tone; label: string }[] = [
  { value: "formal", label: "Formal" },
  { value: "neutral", label: "Neutral" },
  { value: "friendly", label: "Friendly" },
];

/**
 * Draft a letter from a template with [placeholders] for the details. The draft is editable; copy it,
 * download it as a Word file, or save it to the company documents. Nothing here sends names to AI.
 */
export function LetterDraftSheet({
  aiAvailable,
  onOpenChange,
  onSaved,
}: {
  aiAvailable: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [letterType, setLetterType] = useState<LetterType>("welcome");
  const [tone, setTone] = useState<Tone>("neutral");
  const [points, setPoints] = useState<string[]>([""]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function generate(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setBusy(true);
    const keyPoints = points.map((point) => point.trim()).filter((point) => point.length > 0);
    const result = await attempt((c) =>
      c.POST("/ai/letters/draft", {
        body: { letter_type: letterType, tone, key_points: keyPoints },
      }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    setDraft(result.data);
    setText(result.data.body);
  }

  /** The Word file for the text as it now reads, including any edits. */
  async function wordFile(): Promise<Blob | null> {
    if (!draft) return null;
    const result = await attempt((c) =>
      c.POST("/ai/letters/docx", {
        body: { title: draft.title, body: text },
        parseAs: "blob" as const,
      }),
    );
    if (!result.ok) {
      setProblem(result.problem);
      return null;
    }
    return result.data;
  }

  async function download() {
    if (!draft) return;
    setBusy(true);
    const blob = await wordFile();
    setBusy(false);
    if (blob) downloadBlob(blob, `${draft.title}.docx`);
  }

  async function saveAsDocument() {
    if (!draft) return;
    setBusy(true);
    const blob = await wordFile();
    if (!blob) return setBusy(false);
    const form = new FormData();
    form.append("file", blob, `${draft.title}.docx`);
    form.append("title", draft.title);
    form.append("category", "hr_template");
    const result = await attempt((c) =>
      c.POST("/documents", {
        body: { file: "", title: draft.title, category: "hr_template" },
        bodySerializer: () => form,
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Saved to company documents", tone: "success" });
      onSaved();
    } else setProblem(result.problem);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      toast.show({ title: "Draft copied", tone: "success" });
    } catch {
      setProblem({
        code: "COPY_FAILED",
        message: "Select the text and copy it yourself.",
      } as Problem);
    }
  }

  return (
    <FormSheet
      open
      title={aiAvailable ? "Draft with AI" : "Start from template"}
      description={
        aiAvailable
          ? "Choose the letter and tone. Names and identifiers are never sent; the draft uses [placeholders]."
          : "AI is not set up for this company, so you get a template with [placeholders] to fill in."
      }
      onOpenChange={onOpenChange}
      onSubmit={(event) => void generate(event)}
      busy={busy}
      problem={problem}
      saveLabel={draft ? "Start again" : "Create draft"}
    >
      <fieldset disabled={busy} className="flex min-w-0 flex-col gap-4">
        <Select
          label="Letter type"
          value={letterType}
          onChange={(e) => setLetterType(e.target.value as LetterType)}
        >
          {LETTER_TYPES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
        <Select label="Tone" value={tone} onChange={(e) => setTone(e.target.value as Tone)}>
          {TONES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
        <div className="flex flex-col gap-2">
          <p className="text-callout text-label font-medium">Key points (optional)</p>
          <p className="text-footnote text-label-secondary">
            Describe the content only. Do not include email addresses or National Insurance numbers.
          </p>
          {points.map((point, index) => (
            <div key={index} className="flex items-end gap-2">
              <TextField
                label={`Key point ${index + 1}`}
                maxLength={200}
                value={point}
                containerClassName="flex-1"
                onChange={(e) =>
                  setPoints(points.map((item, at) => (at === index ? e.target.value : item)))
                }
              />
              {points.length > 1 && (
                <Button
                  type="button"
                  variant="plain"
                  size="sm"
                  onClick={() => setPoints(points.filter((_, at) => at !== index))}
                >
                  Remove
                </Button>
              )}
            </div>
          ))}
          {points.length < MAX_POINTS && (
            <div>
              <Button
                type="button"
                variant="plain"
                size="sm"
                onClick={() => setPoints([...points, ""])}
              >
                Add a key point
              </Button>
            </div>
          )}
        </div>

        {draft && (
          <section aria-labelledby="letter-draft" className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 id="letter-draft" className="text-headline text-label">
                {draft.title}
              </h3>
              <StatusChip tone={draft.source === "ai" ? "info" : "neutral"}>
                {draft.source === "ai" ? "AI-generated draft" : "Template draft"}
              </StatusChip>
            </div>
            <TextArea
              label="Draft letter"
              rows={16}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="gray" size="sm" onClick={() => void copy()}>
                Copy
              </Button>
              <Button type="button" variant="gray" size="sm" onClick={() => void download()}>
                Download .docx
              </Button>
              <Button
                type="button"
                variant="filled"
                size="sm"
                onClick={() => void saveAsDocument()}
              >
                Save as company document
              </Button>
            </div>
            <p className="text-footnote text-label-secondary">
              Replace each [placeholder] before you send the letter.
            </p>
          </section>
        )}
      </fieldset>
    </FormSheet>
  );
}
