"use client";

import { DatePicker } from "@/components/ui/date-picker";

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
  const text = (label: string, key: keyof RiskAssessment, type = "text") =>
    type === "date" ? (
      <DatePicker
        label={label}
        value={String(form[key]) || null}
        onChange={(value) => set(key, value ?? "")}
      />
    ) : (
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
      <section aria-label="Example scenario" className="space-y-3">
        <p className="text-callout text-label-secondary">
          Example only: adapt every control to your workplace. Loading this replaces and saves the
          current browser draft.
        </p>
        <Button
          type="button"
          variant="gray"
          onClick={() =>
            change({
              ...emptyAssessment(),
              organisation: "Example organisation",
              site: "Office",
              activity: "Office walkways",
              hazards: [
                {
                  ...emptyHazard(),
                  hazard: "Trailing cables",
                  who: "Staff and visitors",
                  controls: "Route cables away from walkways",
                  furtherAction: "Inspect cable routes and secure loose cables",
                  owner: "Site lead",
                },
              ],
            })
          }
        >
          Office walkway example
        </Button>
      </section>
      <section className="grid gap-5 sm:grid-cols-2">
        <h2 className="text-title-2 text-label sm:col-span-2">1. Assessment details</h2>
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
        <h2 className="text-title-2 text-label">2. Hazards</h2>
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
            <DatePicker
              label="Due date"
              value={h.due || null}
              onChange={(value) => setHazard(i, { due: value ?? "" })}
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
      <section
        aria-label="Assessment preview"
        aria-live="polite"
        className="bg-elevated rounded-control space-y-3 p-5"
      >
        <h2 className="text-title-2 text-label">3. Preview and export</h2>
        <p className="text-callout text-label">
          {form.organisation || "Organisation not entered"} · {form.site || "Site not entered"}
        </p>
        <p className="text-callout text-label">
          {form.activity || "Describe the activity to begin your draft."}
        </p>
        <ul className="text-callout text-label space-y-3">
          {form.hazards.map((hazard, index) => (
            <li key={index}>
              <strong>{hazard.hazard || `Hazard ${index + 1} not entered`}</strong>
              <p>
                Who: {hazard.who || "Not entered"}. Controls: {hazard.controls || "Not entered"}.
              </p>
              <p>
                Action: {hazard.furtherAction || "Not entered"}. Owner:{" "}
                {hazard.owner || "Not entered"}. Due: {hazard.due || "Not entered"}. Status:{" "}
                {hazard.status}.
              </p>
            </li>
          ))}
        </ul>
        <p className="text-footnote text-label-secondary">
          {validateAssessment(form).length
            ? "Draft incomplete: finish the required details and acknowledgement before export."
            : "Ready to export. Review the assessment against your workplace before using it."}
        </p>
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
