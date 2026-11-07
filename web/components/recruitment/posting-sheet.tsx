"use client";

import { useEffect, useState, type FormEvent } from "react";

import { useCan } from "@/components/app/session-context";
import { FormSheet } from "@/components/company/form-sheet";
import { FindCodeButton } from "@/components/soc/find-code";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

export type Posting = components["schemas"]["PostingOut"];
type Status = Posting["status"];
type Visibility = Posting["visibility"];
type Visa = Posting["visa_sponsorship"];
type Per = NonNullable<Posting["salary_per"]>;

const VISA: Record<Visa, string> = {
  not_stated: "Not stated",
  available: "Available",
  considered: "Considered for the right candidate",
  not_available: "Not available",
};
const PER: Record<Per, string> = { year: "Per year", month: "Per month", hour: "Per hour" };

// Original starting point for a job description. Placeholders in square brackets are for the hiring manager.
const TEMPLATE = `About the role

[Two or three sentences on what this job is for and where it fits in the team.]

What you will do
- [Main duty one]
- [Main duty two]

What we are looking for
- [Essential skill or experience]
- [Helpful, but not essential, skill or experience]

What we offer
- [Pay, hours and benefits, in plain words]

How to apply
[Closing date and how to apply.]`;

const WRITING_SAFELY = [
  "Describe the tasks of the job, not the kind of person you imagine doing it.",
  "Avoid words such as 'digital native', 'recent graduate' or 'young team'. They can put off people of other ages.",
  "Ask only for what the job needs. Say what the job requires, and offer adjustments for anyone who needs them.",
  "Use neutral wording such as 'you' and 'they'. Words such as 'dominant' or 'rockstar' can put people off.",
  "List only the qualifications the role truly needs.",
  "Say whether visa sponsorship is available, so people know before they apply.",
];

function fieldError(problem: Problem | null, field: string): string | undefined {
  return problem?.field === field ? problem.message : undefined;
}

/** One posting. The public link is shown only while it is external and open; closing it removes the link. */
export function PostingSheet({
  item,
  onOpenChange,
  onSaved,
}: {
  item: Posting | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const can = useCan();
  const toast = useToast();
  const mayWrite = can("recruitment.posting.write");
  const [requisitions, setRequisitions] = useState<{ id: string; title: string }[]>([]);
  const [locations, setLocations] = useState<{ id: string; name: string }[]>([]);
  const [requisition, setRequisition] = useState(item?.requisition_id ?? "");
  const [title, setTitle] = useState(item?.title ?? "");
  const [visibility, setVisibility] = useState<Visibility>(item?.visibility ?? "internal");
  const [location, setLocation] = useState(item?.location_id ?? "");
  const [jobCode, setJobCode] = useState(item?.job_code ?? "");
  const [socCode, setSocCode] = useState(item?.soc_code ?? "");
  const [vacancies, setVacancies] = useState(String(item?.vacancies ?? 1));
  const [posted, setPosted] = useState(item?.posted_on ?? "");
  const [closes, setCloses] = useState(item?.closes_on ?? "");
  const [email, setEmail] = useState(item?.contact_email ?? "");
  const [phone, setPhone] = useState(item?.contact_phone ?? "");
  const [from, setFrom] = useState(item?.salary_from ?? "");
  const [to, setTo] = useState(item?.salary_to ?? "");
  const [per, setPer] = useState<Per | "">(item?.salary_per ?? "");
  const [hours, setHours] = useState(item?.weekly_hours ?? "");
  const [description, setDescription] = useState(item?.description ?? "");
  const [visa, setVisa] = useState<Visa>(item?.visa_sponsorship ?? "not_stated");
  const [status, setStatus] = useState<Status>(item?.status ?? "draft");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([
      attempt((c) => c.GET("/requisitions", { params: { query: { status: "open", limit: 100 } } })),
      attempt((c) => c.GET("/locations")),
    ]).then(([reqs, locs]) => {
      if (!active) return;
      if (reqs.ok)
        setRequisitions(reqs.data.items.map((row) => ({ id: row.id, title: row.job_title })));
      if (locs.ok) setLocations(locs.data.map((row) => ({ id: row.id, name: row.name })));
    });
    return () => {
      active = false;
    };
  }, []);

  function body() {
    return {
      requisition_id: requisition,
      title: title.trim(),
      visibility,
      location_id: location || null,
      job_code: jobCode.trim() || null,
      soc_code: socCode.trim() || null,
      vacancies: Number(vacancies),
      posted_on: posted || null,
      closes_on: closes || null,
      contact_email: email.trim() || null,
      contact_phone: phone.trim() || null,
      salary_from: from === "" ? null : String(from),
      salary_to: to === "" ? null : String(to),
      salary_per: per || null,
      weekly_hours: hours === "" ? null : String(hours),
      description: description.trim() || null,
      visa_sponsorship: visa,
    };
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!title.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the posting title.",
        field: "title",
      } as Problem);
    if (!requisition)
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Choose an open requisition.",
        field: "requisition_id",
      } as Problem);
    setBusy(true);
    const result = item
      ? await attempt((c) =>
          c.PATCH("/postings/{posting_id}", {
            params: { path: { posting_id: item.id } },
            body: body(),
          }),
        )
      : await attempt((c) => c.POST("/postings", { body: body() }));
    if (!result.ok) {
      setBusy(false);
      return setProblem(result.problem);
    }
    if (item && status !== item.status) {
      const changed = await attempt((c) =>
        c.PATCH("/postings/{posting_id}/status", {
          params: { path: { posting_id: result.data.id } },
          body: { status },
        }),
      );
      setBusy(false);
      if (!changed.ok) return setProblem(changed.problem);
    } else setBusy(false);
    toast.show({ title: item ? "Posting saved" : "Posting created", tone: "success" });
    onSaved();
  }

  async function setPostingStatus(next: Status) {
    if (!item) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.PATCH("/postings/{posting_id}/status", {
        params: { path: { posting_id: item.id } },
        body: { status: next },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({
        title: next === "closed" ? "Posting closed" : "Posting opened",
        tone: "success",
      });
      onSaved();
    } else setProblem(result.problem);
  }

  return (
    <FormSheet
      open
      title={item ? "Posting" : "New posting"}
      description="Only an open requisition can be advertised. Closing a posting removes its public link straight away."
      onOpenChange={onOpenChange}
      onSubmit={(event) => void save(event)}
      busy={busy}
      problem={problem}
      saveLabel={item ? "Save changes" : "Create posting"}
    >
      <fieldset disabled={busy || !mayWrite} className="flex min-w-0 flex-col gap-4">
        <Select
          label="Requisition"
          value={requisition}
          onChange={(e) => setRequisition(e.target.value)}
          error={fieldError(problem, "requisition_id")}
        >
          <option value="">Choose an open requisition</option>
          {requisitions.map((row) => (
            <option key={row.id} value={row.id}>
              {row.title}
            </option>
          ))}
        </Select>
        <TextField
          label="Posting title"
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={fieldError(problem, "title")}
        />
        <Select
          label="Visibility"
          value={visibility}
          onChange={(e) => setVisibility(e.target.value as Visibility)}
        >
          <option value="internal">Internal (staff only)</option>
          <option value="external">External (public careers page)</option>
        </Select>
        <Select label="Location" value={location} onChange={(e) => setLocation(e.target.value)}>
          <option value="">No location</option>
          {locations.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </Select>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Job code (optional)"
            maxLength={40}
            value={jobCode}
            onChange={(e) => setJobCode(e.target.value)}
          />
          <div className="flex items-end gap-2">
            <TextField
              label="SOC code (optional)"
              maxLength={4}
              inputMode="numeric"
              value={socCode}
              onChange={(e) => setSocCode(e.target.value)}
              hint="Four digits, for example 8111."
              error={fieldError(problem, "soc_code")}
              containerClassName="flex-1"
            />
            <FindCodeButton onFound={setSocCode} />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Vacancies"
            type="number"
            min={1}
            max={999}
            required
            value={vacancies}
            onChange={(e) => setVacancies(e.target.value)}
          />
          <TextField
            label="Hours a week (optional)"
            type="number"
            min={0}
            max={168}
            step="0.5"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Posted on (optional)"
            type="date"
            value={posted}
            onChange={(e) => setPosted(e.target.value)}
          />
          <TextField
            label="Closes on (optional)"
            type="date"
            value={closes}
            onChange={(e) => setCloses(e.target.value)}
            error={fieldError(problem, "closes_on")}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Contact email (optional)"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldError(problem, "contact_email")}
          />
          <TextField
            label="Contact phone (optional)"
            maxLength={40}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Salary from (optional)"
            type="number"
            min={0}
            step="0.01"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            error={fieldError(problem, "salary_from")}
          />
          <TextField
            label="Salary to (optional)"
            type="number"
            min={0}
            step="0.01"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            error={fieldError(problem, "salary_to")}
          />
        </div>
        <Select label="Salary is" value={per} onChange={(e) => setPer(e.target.value as Per | "")}>
          <option value="">Not stated</option>
          {(Object.keys(PER) as Per[]).map((value) => (
            <option key={value} value={value}>
              {PER[value]}
            </option>
          ))}
        </Select>
        <Select
          label="Visa sponsorship"
          value={visa}
          onChange={(e) => setVisa(e.target.value as Visa)}
        >
          {(Object.keys(VISA) as Visa[]).map((value) => (
            <option key={value} value={value}>
              {VISA[value]}
            </option>
          ))}
        </Select>
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button
              type="button"
              variant="plain"
              size="sm"
              onClick={() => {
                if (!description.trim() || window.confirm("Replace the text with the template?"))
                  setDescription(TEMPLATE);
              }}
            >
              Start from template
            </Button>
          </div>
          <TextArea
            label="Job description"
            rows={12}
            maxLength={20000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <details className="border-separator rounded-xl border p-3">
            <summary className="text-callout text-accent-text cursor-pointer font-medium">
              Writing it safely
            </summary>
            <ul className="text-callout text-label-secondary mt-3 list-disc pl-5">
              {WRITING_SAFELY.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </details>
        </div>
        {item && (
          <div className="flex flex-col gap-3">
            <Select
              label="Status"
              value={status}
              onChange={(e) => setStatus(e.target.value as Status)}
            >
              <option value="draft">Draft</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
            </Select>
            {item.public_link && (
              <p className="text-footnote text-label-secondary break-all">
                Public link: {item.public_link}
              </p>
            )}
            {item.status !== "closed" ? (
              <ConfirmDialog
                trigger={
                  <Button type="button" variant="plain" disabled={busy || !mayWrite}>
                    Close posting
                  </Button>
                }
                title="Close this posting?"
                description="Applications stop and the public link stops working straight away."
                confirmLabel="Close posting"
                destructive
                onConfirm={() => setPostingStatus("closed")}
              />
            ) : null}
          </div>
        )}
        {problem && !problem.field && <Alert tone="danger" title={problem.message} />}
      </fieldset>
    </FormSheet>
  );
}
