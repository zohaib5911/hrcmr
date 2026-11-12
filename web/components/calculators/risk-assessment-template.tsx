"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import {
  buildDocx,
  buildPdf,
  clearAssessment,
  emptyAssessment,
  emptyHazard,
  loadAssessment,
  saveAssessment,
  validateAssessment,
  type Hazard,
  type RiskAssessment,
} from "@/lib/calculators/risk-assessment-template";

function download(data: Uint8Array, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([data as BlobPart], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function RiskAssessmentTemplate() {
  const [form, setForm] = useState<RiskAssessment>(emptyAssessment);
  const [errors, setErrors] = useState<string[]>([]);
  const [note, setNote] = useState("");

  useEffect(() => {
    const saved = loadAssessment();
    if (saved) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm(saved);
      setNote("Restored your draft from this browser.");
    }
  }, []);

  function change(next: RiskAssessment) {
    setForm(next);
    setErrors([]);
    setNote(
      saveAssessment(next)
        ? "Draft saved in this browser only."
        : "Could not save in this browser.",
    );
  }
  const set = (key: keyof RiskAssessment, value: string | boolean) =>
    change({ ...form, [key]: value });
  const setHazard = (i: number, patch: Partial<Hazard>) =>
    change({ ...form, hazards: form.hazards.map((h, n) => (n === i ? { ...h, ...patch } : h)) });
  function exportAs(kind: "pdf" | "docx") {
    const problems = validateAssessment(form);
    setErrors(problems);
    if (problems.length) return;
    if (kind === "pdf") download(buildPdf(form), "risk-assessment.pdf", "application/pdf");
    else
      download(
        buildDocx(form),
        "risk-assessment.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      );
  }
  const text = (label: string, key: keyof RiskAssessment, type = "text") => (
    <TextField
      label={label}
      type={type}
      clearable={false}
      value={String(form[key])}
      onChange={(e) => set(key, e.target.value)}
    />
  );

  return (
    <form noValidate className="space-y-8" onSubmit={(e) => e.preventDefault()}>
      <section className="grid gap-5 sm:grid-cols-2">
        <h2 className="text-title-2 text-label sm:col-span-2">Assessment details</h2>
        {text("Organisation", "organisation")}
        {text("Site", "site")}
        <Select
          label="Country"
          value={form.country}
          onChange={(e) => set("country", e.target.value)}
        >
          {["England", "Scotland", "Wales", "Northern Ireland"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </Select>
        {text("Number of employees", "employees", "number")}
        {text("Assessor", "assessor")}
        {text("Date assessed", "assessedOn", "date")}
        {text("Review date", "reviewOn", "date")}
        {text("Reference", "reference")}
        {text("Version", "version")}
        <div className="sm:col-span-2">
          <TextArea
            label="Activity or area assessed"
            value={form.activity}
            onChange={(e) => set("activity", e.target.value)}
          />
        </div>
        <TextArea
          label="People consulted"
          value={form.consulted}
          onChange={(e) => set("consulted", e.target.value)}
        />
        <TextArea
          label="Groups at particular risk"
          value={form.atRiskGroups}
          onChange={(e) => set("atRiskGroups", e.target.value)}
        />
      </section>
      <section className="space-y-6">
        <h2 className="text-title-2 text-label">Hazards</h2>
        {form.hazards.map((h, i) => (
          <fieldset
            key={i}
            className="border-separator grid gap-4 rounded-xl border p-4 sm:grid-cols-2"
          >
            <legend className="text-callout text-label px-2">Hazard {i + 1}</legend>
            <TextField
              label="Hazard"
              clearable={false}
              value={h.hazard}
              onChange={(e) => setHazard(i, { hazard: e.target.value })}
            />
            <TextField
              label="Who might be harmed"
              clearable={false}
              value={h.who}
              onChange={(e) => setHazard(i, { who: e.target.value })}
            />
            <TextArea
              label="Controls in place"
              value={h.controls}
              onChange={(e) => setHazard(i, { controls: e.target.value })}
            />
            <TextArea
              label="Further action"
              value={h.furtherAction}
              onChange={(e) => setHazard(i, { furtherAction: e.target.value })}
            />
            <TextField
              label="Owner"
              clearable={false}
              value={h.owner}
              onChange={(e) => setHazard(i, { owner: e.target.value })}
            />
            <TextField
              label="Due date"
              type="date"
              clearable={false}
              value={h.due}
              onChange={(e) => setHazard(i, { due: e.target.value })}
            />
            <Select
              label="Status"
              value={h.status}
              onChange={(e) => setHazard(i, { status: e.target.value as Hazard["status"] })}
            >
              <option value="open">Open</option>
              <option value="in-progress">In progress</option>
              <option value="done">Done</option>
            </Select>
            {form.hazards.length > 1 ? (
              <div className="flex items-end">
                <Button
                  type="button"
                  variant="gray"
                  onClick={() =>
                    change({ ...form, hazards: form.hazards.filter((_, n) => n !== i) })
                  }
                >
                  Remove hazard
                </Button>
              </div>
            ) : null}
          </fieldset>
        ))}
        <Button
          type="button"
          variant="gray"
          onClick={() => change({ ...form, hazards: [...form.hazards, emptyHazard()] })}
        >
          Add hazard
        </Button>
      </section>
      <Checkbox
        label="I confirm this assessment reflects the work as done and will be reviewed."
        checked={form.acknowledgement}
        onCheckedChange={(v) => set("acknowledgement", v === true)}
      />
      <div className="flex flex-wrap gap-3">
        <Button type="button" onClick={() => exportAs("pdf")}>
          Download PDF
        </Button>
        <Button type="button" onClick={() => exportAs("docx")}>
          Download DOCX
        </Button>
        <Button
          type="button"
          variant="gray"
          onClick={() => {
            clearAssessment();
            setForm(emptyAssessment());
            setErrors([]);
            setNote("Draft cleared from this browser.");
          }}
        >
          Clear saved draft
        </Button>
      </div>
      {errors.length ? (
        <ul role="alert" className="text-callout text-label list-disc pl-5">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}
      <p role="status" className="text-footnote text-label-secondary">
        {note}
      </p>
    </form>
  );
}
