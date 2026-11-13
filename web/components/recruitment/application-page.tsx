"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Select } from "@/components/ui/select";
import { Stepper } from "@/components/ui/stepper";
import { StatusChip } from "@/components/ui/status-chip";
import { TextArea } from "@/components/ui/text-area";
import { DatePicker } from "@/components/ui/date-picker";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { downloadBlob } from "@/lib/attendance";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk, formatUkDateTime } from "@/lib/ui/dates";

import { ConvertSheet } from "./convert-sheet";
import { RTW_STATUS } from "./rtw";
import {
  ALL_STAGES,
  FORWARD_STAGES,
  STAGE_LABEL,
  STAGE_TONE,
  nextStage,
  waitingOn,
  type Stage,
} from "./stages";

type Application = components["schemas"]["ApplicationOut"];
type Interview = components["schemas"]["InterviewOut"];
type Offer = components["schemas"]["OfferOut"];
type OfferStatus = Offer["status"];
type Mode = Interview["mode"];
type Outcome = Interview["outcome"];
type Per = Offer["salary_per"];

const MODE: Record<Mode, string> = { in_person: "In person", video: "Video call", phone: "Phone" };
const OUTCOME: Record<Outcome, string> = {
  pending: "Pending",
  passed: "Passed",
  failed: "Failed",
  no_show: "No show",
};
const OFFER_STATUS: Record<
  OfferStatus,
  { label: string; tone: "neutral" | "success" | "warning" | "info" | "danger" }
> = {
  draft: { label: "Draft", tone: "neutral" },
  sent: { label: "Sent", tone: "info" },
  accepted: { label: "Accepted", tone: "success" },
  declined: { label: "Declined", tone: "danger" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};
const PER: Record<Per, string> = { year: "a year", month: "a month", hour: "an hour" };

/** "Offer Letter" -> "Offer letter" for the progress steps; stage identifiers stay as they are. */
function sentenceCase(label: string): string {
  return label.charAt(0) + label.slice(1).toLowerCase();
}

function gbp(value: string): string {
  const number = Number(value);
  return Number.isNaN(number)
    ? value
    : new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(number);
}

/** One application: where it stands, how to move it, its history, and its interviews and offers. */
export function ApplicationPage({ applicationId }: { applicationId: string }) {
  const can = useCan();
  const mayRead = can("recruitment.application.read");
  const mayWrite = can("recruitment.application.write");
  const [app, setApp] = useState<Application | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [converting, setConverting] = useState(false);
  const toast = useToast();
  const mayConvert = can("recruitment.candidate.convert") && can("employee.profile.write");

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void attempt((c) =>
      c.GET("/applications/{application_id}/offers", {
        params: { path: { application_id: applicationId } },
      }),
    ).then((result) => {
      if (active && result.ok) setOffers(result.data);
    });
    return () => {
      active = false;
    };
  }, [mayRead, applicationId, version]);

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void attempt((c) =>
      c.GET("/applications/{application_id}", {
        params: { path: { application_id: applicationId } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) {
        setApp(result.data);
        setProblem(null);
      } else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead, applicationId, version]);

  if (!mayRead) return <Alert tone="danger" title="Applications are for HR and recruiters." />;
  if (problem && !app) return <Alert tone="danger" title={problem.message} />;
  if (!app) return <p className="text-callout text-label-secondary">Loading application…</p>;

  // Hired is set only by Convert to employee, so it is never offered as a move.
  const following = nextStage(app.stage);
  const next = following === "hired" ? null : following;
  const ended = app.stage === "rejected" || app.stage === "withdrawn";
  const reached = Math.max(
    0,
    ...app.stage_history
      .map((entry) => FORWARD_STAGES.indexOf(entry.stage))
      .filter((index) => index >= 0),
  );

  async function move(stage: Stage) {
    setBusy(true);
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/applications/{application_id}/stage", {
        params: { path: { application_id: applicationId } },
        body: { stage },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: `Moved to ${STAGE_LABEL[stage]}`, tone: "success" });
      setVersion((n) => n + 1);
    } else setProblem(result.problem);
  }

  return (
    <div className="flex flex-col gap-6">
      <Link href="/recruitment" className="text-callout text-accent-text underline">
        Back to recruitment
      </Link>
      <header className="flex flex-col gap-3">
        <h1 className="text-large-title text-label break-words">
          {app.candidate_name} — {app.posting_title}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip tone={STAGE_TONE[app.stage]}>{STAGE_LABEL[app.stage]}</StatusChip>
          <StatusChip tone={RTW_STATUS[app.candidate_rtw_status].tone}>
            Right to work: {RTW_STATUS[app.candidate_rtw_status].label}
          </StatusChip>
        </div>
        <p className="text-callout text-label-secondary">{waitingOn(app.stage)}</p>
        {mayWrite && (
          <div className="flex flex-wrap items-end gap-3">
            {next && (
              <Button variant="filled" disabled={busy} onClick={() => void move(next)}>
                Move to {STAGE_LABEL[next]}
              </Button>
            )}
            {!ended && app.stage !== "hired" && (
              <div className="w-64">
                <Select
                  label="Move to stage"
                  value={app.stage}
                  disabled={busy}
                  onChange={(e) => {
                    const stage = e.target.value as Stage;
                    if (stage !== app.stage) void move(stage);
                  }}
                >
                  {ALL_STAGES.filter((stage) => stage !== "hired").map((stage) => (
                    <option key={stage} value={stage}>
                      {STAGE_LABEL[stage]}
                    </option>
                  ))}
                </Select>
              </div>
            )}
          </div>
        )}
        {mayConvert &&
          app.stage !== "hired" &&
          app.stage !== "rejected" &&
          app.stage !== "withdrawn" && (
            <ConvertControl
              accepted={offers.find((offer) => offer.status === "accepted")}
              verified={app.candidate_rtw_status === "verified"}
              busy={busy}
              onOpen={() => setConverting(true)}
            />
          )}
        {problem && <Alert tone="danger" title={problem.message} />}
      </header>

      <Card className="flex flex-col gap-4 p-5">
        <Stepper
          steps={FORWARD_STAGES.map((stage) => ({
            id: stage,
            label: sentenceCase(STAGE_LABEL[stage]),
          }))}
          current={ended ? reached : Math.max(0, FORWARD_STAGES.indexOf(app.stage))}
          orientation="responsive"
        />
        <section aria-labelledby="history" className="flex flex-col gap-2">
          <h2 id="history" className="text-headline text-label font-semibold">
            History
          </h2>
          <ul className="flex flex-col gap-1 text-callout">
            {app.stage_history.map((entry, index) => (
              <li key={`${entry.stage}-${index}`} className="flex flex-wrap justify-between gap-2">
                <span>{STAGE_LABEL[entry.stage]}</span>
                <span className="text-label-secondary">{formatUkDateTime(entry.at)}</span>
              </li>
            ))}
          </ul>
        </section>
      </Card>

      {converting && (
        <ConvertSheet
          application={app}
          startDate={offers.find((offer) => offer.status === "accepted")?.start_date ?? null}
          onOpenChange={(open) => {
            if (!open) setConverting(false);
          }}
        />
      )}
      <InterviewsPanel
        application={app}
        mayWrite={mayWrite}
        onChanged={() => setVersion((n) => n + 1)}
      />
      <OffersPanel
        application={app}
        mayWrite={mayWrite}
        onChanged={() => setVersion((n) => n + 1)}
      />
    </div>
  );
}

function InterviewsPanel({
  application,
  mayWrite,
  onChanged,
}: {
  application: Application;
  mayWrite: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [items, setItems] = useState<Interview[] | null>(null);
  const [people, setPeople] = useState<{ id: string; name: string }[]>([]);
  const [version, setVersion] = useState(0);
  const [when, setWhen] = useState("");
  const [duration, setDuration] = useState("60");
  const [mode, setMode] = useState<Mode>("video");
  const [where, setWhere] = useState("");
  const [panel, setPanel] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/applications/{application_id}/interviews", {
        params: { path: { application_id: application.id } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setItems(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [application.id, version]);

  useEffect(() => {
    if (!mayWrite) return;
    let active = true;
    void attempt((c) => c.GET("/employees", { params: { query: { status: "active" } } })).then(
      (result) => {
        if (active && result.ok)
          setPeople(
            result.data.employees.map((row) => ({
              id: row.id,
              name: `${row.first_name} ${row.last_name}`,
            })),
          );
      },
    );
    return () => {
      active = false;
    };
  }, [mayWrite]);

  async function schedule(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!when)
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Choose the date and time.",
        field: "scheduled_at",
      } as Problem);
    const result = await attempt((c) =>
      c.POST("/applications/{application_id}/interviews", {
        params: { path: { application_id: application.id } },
        body: {
          scheduled_at: new Date(when).toISOString(),
          duration_minutes: Number(duration),
          mode,
          location_or_link: where.trim() || null,
          interviewer_employee_ids: panel,
          notes: notes.trim() || null,
        },
      }),
    );
    if (!result.ok) return setProblem(result.problem);
    toast.show({ title: "Interview booked. Invitations are on their way.", tone: "success" });
    setWhen("");
    setWhere("");
    setPanel([]);
    setNotes("");
    setVersion((n) => n + 1);
    onChanged();
  }

  async function setOutcome(interview: Interview, outcome: Outcome) {
    const result = await attempt((c) =>
      c.PATCH("/applications/{application_id}/interviews/{interview_id}", {
        params: { path: { application_id: application.id, interview_id: interview.id } },
        body: { outcome },
      }),
    );
    if (result.ok) setVersion((n) => n + 1);
    else setProblem(result.problem);
  }

  async function download(interview: Interview) {
    const result = await attempt((c) =>
      c.GET("/applications/{application_id}/interviews/{interview_id}/invite.ics", {
        params: { path: { application_id: application.id, interview_id: interview.id } },
        parseAs: "blob" as const,
      }),
    );
    if (result.ok)
      downloadBlob(result.data, `interview-${formatUk(interview.scheduled_at.slice(0, 10))}.ics`);
    else setProblem(result.problem);
  }

  return (
    <section aria-labelledby="interviews" className="flex flex-col gap-4">
      <h2 id="interviews" className="text-title-3 text-label font-semibold">
        Interviews
      </h2>
      {problem && <Alert tone="danger" title={problem.message} />}
      {items && items.length === 0 && (
        <p className="text-callout text-label-secondary">No interviews yet.</p>
      )}
      <ul className="flex flex-col gap-3">
        {(items ?? []).map((interview) => (
          <li
            key={interview.id}
            className="border-separator flex flex-col gap-2 rounded-xl border p-4"
          >
            <div className="flex flex-wrap justify-between gap-2">
              <span className="text-body">
                {formatUkDateTime(interview.scheduled_at)} · {interview.duration_minutes} min
              </span>
              <span className="text-callout text-label-secondary">
                {MODE[interview.mode]}
                {interview.location_or_link ? ` · ${interview.location_or_link}` : ""}
              </span>
            </div>
            <p className="text-callout text-label-secondary">
              Panel:{" "}
              {interview.interviewers.length
                ? interview.interviewers.map((row) => row.name).join(", ")
                : "not set"}
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-48">
                <Select
                  label="Outcome"
                  value={interview.outcome}
                  disabled={!mayWrite}
                  onChange={(e) => void setOutcome(interview, e.target.value as Outcome)}
                >
                  {(Object.keys(OUTCOME) as Outcome[]).map((value) => (
                    <option key={value} value={value}>
                      {OUTCOME[value]}
                    </option>
                  ))}
                </Select>
              </div>
              <Button variant="gray" size="sm" onClick={() => void download(interview)}>
                Add to calendar (.ics)
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {mayWrite && (
        <form onSubmit={(e) => void schedule(e)} className="flex flex-col gap-4" noValidate>
          <h3 className="text-headline text-label font-semibold">Book an interview</h3>
          <DateTimePicker
            legend="Interview date and time"
            dateLabel="Interview date"
            timeLabel="Interview time"
            required
            value={when || null}
            onChange={(picked) => setWhen(picked ?? "")}
            error={problem?.field === "scheduled_at" ? problem.message : undefined}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Duration (minutes)"
              type="number"
              min={5}
              max={480}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
            <Select label="Format" value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              {(Object.keys(MODE) as Mode[]).map((value) => (
                <option key={value} value={value}>
                  {MODE[value]}
                </option>
              ))}
            </Select>
          </div>
          <TextField
            label="Location or link (optional)"
            maxLength={300}
            value={where}
            onChange={(e) => setWhere(e.target.value)}
          />
          <fieldset className="flex flex-col gap-2">
            <legend className="text-callout text-label mb-1 font-medium">Interviewers</legend>
            {people.length === 0 && (
              <p className="text-callout text-label-secondary">No current people to choose yet.</p>
            )}
            <div className="flex max-h-56 flex-col gap-2 overflow-y-auto">
              {people.map((person) => (
                <Checkbox
                  key={person.id}
                  label={person.name}
                  checked={panel.includes(person.id)}
                  onCheckedChange={(value) =>
                    setPanel(
                      value === true
                        ? [...panel, person.id]
                        : panel.filter((id) => id !== person.id),
                    )
                  }
                />
              ))}
            </div>
          </fieldset>
          <TextArea
            label="Notes for the panel (optional)"
            rows={3}
            maxLength={5000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <div>
            <Button type="submit" variant="filled">
              Book interview
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

function OffersPanel({
  application,
  mayWrite,
  onChanged,
}: {
  application: Application;
  mayWrite: boolean;
  onChanged: () => void;
}) {
  const [items, setItems] = useState<Offer[] | null>(null);
  const [version, setVersion] = useState(0);
  const [role, setRole] = useState("");
  const [salary, setSalary] = useState("");
  const [per, setPer] = useState<Per>("year");
  const [start, setStart] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/applications/{application_id}/offers", {
        params: { path: { application_id: application.id } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setItems(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [application.id, version]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!role.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the role title.",
        field: "role_title",
      } as Problem);
    if (salary === "")
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the salary.",
        field: "salary",
      } as Problem);
    const result = await attempt((c) =>
      c.POST("/applications/{application_id}/offers", {
        params: { path: { application_id: application.id } },
        body: {
          role_title: role.trim(),
          salary: String(salary),
          salary_per: per,
          start_date: start || null,
        },
      }),
    );
    if (!result.ok) return setProblem(result.problem);
    setRole("");
    setSalary("");
    setStart("");
    setVersion((n) => n + 1);
    onChanged();
  }

  async function change(offer: Offer, status: OfferStatus) {
    const result = await attempt((c) =>
      c.PATCH("/offers/{offer_id}", { params: { path: { offer_id: offer.id } }, body: { status } }),
    );
    if (result.ok) {
      setVersion((n) => n + 1);
      onChanged();
    } else setProblem(result.problem);
  }

  const followUps: Record<OfferStatus, OfferStatus[]> = {
    draft: ["sent", "withdrawn"],
    sent: ["accepted", "declined", "withdrawn"],
    accepted: [],
    declined: [],
    withdrawn: [],
  };
  const labels: Record<OfferStatus, string> = {
    draft: "Draft",
    sent: "Mark as sent",
    accepted: "Mark as accepted",
    declined: "Mark as declined",
    withdrawn: "Withdraw",
  };

  return (
    <section aria-labelledby="offers" className="flex flex-col gap-4">
      <h2 id="offers" className="text-title-3 text-label font-semibold">
        Offers
      </h2>
      {problem && <Alert tone="danger" title={problem.message} />}
      {items && items.length === 0 && (
        <p className="text-callout text-label-secondary">No offers yet.</p>
      )}
      <ul className="flex flex-col gap-3">
        {(items ?? []).map((offer) => (
          <li key={offer.id} className="border-separator flex flex-col gap-2 rounded-xl border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-body">
                {offer.role_title} · {gbp(offer.salary)} {PER[offer.salary_per]}
                {offer.start_date ? ` · starts ${formatUk(offer.start_date)}` : ""}
              </span>
              <StatusChip tone={OFFER_STATUS[offer.status].tone}>
                {OFFER_STATUS[offer.status].label}
              </StatusChip>
            </div>
            {mayWrite && followUps[offer.status].length > 0 && (
              <div className="flex flex-wrap gap-2">
                {followUps[offer.status].map((status) => (
                  <Button
                    key={status}
                    variant="gray"
                    size="sm"
                    onClick={() => void change(offer, status)}
                  >
                    {labels[status]}
                  </Button>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>

      {mayWrite && application.stage !== "rejected" && application.stage !== "withdrawn" && (
        <form onSubmit={(e) => void create(e)} className="flex flex-col gap-4" noValidate>
          <h3 className="text-headline text-label font-semibold">Make an offer</h3>
          <TextField
            label="Role title"
            required
            maxLength={200}
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Salary (GBP)"
              type="number"
              min={0}
              step="0.01"
              required
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
            />
            <Select label="Salary is" value={per} onChange={(e) => setPer(e.target.value as Per)}>
              {(Object.keys(PER) as Per[]).map((value) => (
                <option key={value} value={value}>
                  {PER[value].replace(/^a /, "per ")}
                </option>
              ))}
            </Select>
          </div>
          <DatePicker
            label="Start date (optional)"
            value={start || null}
            onChange={(picked) => setStart(picked ?? "")}
          />
          <div>
            <Button type="submit" variant="filled">
              Save offer as draft
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

/** The Convert button: enabled only when there is an accepted offer and a verified right-to-work check. */
function ConvertControl({
  accepted,
  verified,
  busy,
  onOpen,
}: {
  accepted: Offer | undefined;
  verified: boolean;
  busy: boolean;
  onOpen: () => void;
}) {
  const ready = Boolean(accepted) && verified;
  const reason = !accepted
    ? "Needs an accepted offer."
    : !verified
      ? "Needs a verified right-to-work check."
      : "";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="filled" disabled={!ready || busy} onClick={onOpen}>
        Convert to employee
      </Button>
      {!ready && <span className="text-callout text-label-secondary">{reason}</span>}
    </div>
  );
}
