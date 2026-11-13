"use client";

import { PublicDate } from "@/components/marketing/public-content";

import { DatePicker } from "@/components/ui/date-picker";

import { useMemo, useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import {
  calculateDeadline,
  eventKinds,
  type Nation,
} from "@/lib/calculators/sponsor-reporting-deadline-calculator";

const today = () => new Date().toISOString().slice(0, 10);

type Form = { eventId: string; eventDate: string; nation: Nation };

const initial: Form = {
  eventId: eventKinds[0]?.id ?? "",
  eventDate: "",
  nation: "england-and-wales",
};

/** Example events: they only fill in the form; the deadline comes from the same rules. */
export const deadlinePresets: readonly CalculatorPreset<Form>[] = [
  {
    id: "no-start",
    label: "Worker did not start, Scotland",
    values: { eventId: "no-start", eventDate: "2026-11-27", nation: "scotland" },
  },
  {
    id: "org-change",
    label: "Change to your organisation over the August bank holiday",
    values: { eventId: "org-change", eventDate: "2026-08-28", nation: "england-and-wales" },
  },
  {
    id: "pay-rise",
    label: "Salary increase",
    values: { eventId: "pay-rise", eventDate: "", nation: "england-and-wales" },
  },
];

export function SponsorReportingDeadlineCalculator() {
  const [form, setForm] = useState<Form>(initial);
  const [touched, setTouched] = useState(false);
  // Live result: recalculated locally on every change once the user has answered something.
  const result = useMemo(
    () => (touched ? calculateDeadline({ ...form, today: today() }) : null),
    [form, touched],
  );
  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setTouched(true);
  }

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
        <PresetChips
          presets={deadlinePresets}
          onSelect={(preset) => {
            setForm(preset.values);
            setTouched(true);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> The event
        </h2>
        <Select
          label="Event type"
          value={form.eventId}
          onChange={(event) => update("eventId", event.target.value)}
        >
          {eventKinds.map((kind) => (
            <option key={kind.id} value={kind.id}>
              {kind.label}
            </option>
          ))}
        </Select>
        <DatePicker
          label="Event date"
          hint="The date the event happened, or the date you became aware of it for organisation changes."
          value={form.eventDate || null}
          onChange={(value) => update("eventDate", value ?? "")}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">2.</span> Where you are
        </h2>
        <Select
          label="Nation (bank holidays)"
          value={form.nation}
          onChange={(event) => update("nation", event.target.value as Nation)}
        >
          <option value="england-and-wales">England and Wales</option>
          <option value="scotland">Scotland</option>
          <option value="northern-ireland">Northern Ireland</option>
        </Select>
        <Button
          variant="gray"
          onClick={() => {
            setForm(initial);
            setTouched(false);
          }}
        >
          Reset answers
        </Button>
      </form>
      <section
        aria-label="Deadline result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">Your deadline</h2>
            {result.reportable && !result.deadline ? (
              <p role="status" className="text-callout text-label mt-2">
                Incomplete: a deadline can’t be shown yet. See the note below.
              </p>
            ) : null}
            <dl className="text-callout text-label mt-4 space-y-3">
              <div>
                <dt className="font-semibold">Reportable?</dt>
                <dd>{result.reportable ? "Yes" : "No fixed reporting deadline"}</dd>
              </div>
              {result.deadline ? (
                <>
                  <div>
                    <dt className="font-semibold">Latest date to report</dt>
                    <dd>
                      <PublicDate value={result.deadline} />
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold">Working days left</dt>
                    <dd>
                      {result.overdue
                        ? "Overdue: report as soon as possible"
                        : (result.daysLeft ?? "Unknown")}
                    </dd>
                  </div>
                </>
              ) : null}
            </dl>
            <div className="text-callout text-label-secondary mt-4 space-y-3">
              {result.explanation.map((text) => (
                <p key={text}>{text}</p>
              ))}
            </div>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Choose the event and its date, or pick an example; the deadline updates as you go.
          </p>
        )}
      </section>
    </div>
  );
}
