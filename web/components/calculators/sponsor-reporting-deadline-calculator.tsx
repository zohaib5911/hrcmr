"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateDeadline,
  eventKinds,
  type DeadlineResult,
  type Nation,
} from "@/lib/calculators/sponsor-reporting-deadline-calculator";

const today = () => new Date().toISOString().slice(0, 10);

export function SponsorReportingDeadlineCalculator() {
  const [eventId, setEventId] = useState(eventKinds[0]?.id ?? "");
  const [eventDate, setEventDate] = useState("");
  const [nation, setNation] = useState<Nation>("england-and-wales");
  const [result, setResult] = useState<DeadlineResult | null>(null);

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          setResult(calculateDeadline({ eventId, eventDate, nation, today: today() }));
        }}
      >
        <h2 className="text-title-2 text-label">The event</h2>
        <Select
          label="Event type"
          value={eventId}
          onChange={(event) => {
            setEventId(event.target.value);
            setResult(null);
          }}
        >
          {eventKinds.map((kind) => (
            <option key={kind.id} value={kind.id}>
              {kind.label}
            </option>
          ))}
        </Select>
        <TextField
          label="Event date"
          type="date"
          clearable={false}
          hint="The date the event happened, or the date you became aware of it for organisation changes."
          value={eventDate}
          onChange={(event) => {
            setEventDate(event.target.value);
            setResult(null);
          }}
        />
        <Select
          label="Nation (bank holidays)"
          value={nation}
          onChange={(event) => {
            setNation(event.target.value as Nation);
            setResult(null);
          }}
        >
          <option value="england-and-wales">England and Wales</option>
          <option value="scotland">Scotland</option>
          <option value="northern-ireland">Northern Ireland</option>
        </Select>
        <Button type="submit">Work out the deadline</Button>
      </form>
      <section
        aria-label="Deadline result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">Your deadline</h2>
            <dl className="text-callout text-label mt-4 space-y-3">
              <div>
                <dt className="font-semibold">Reportable?</dt>
                <dd>{result.reportable ? "Yes" : "No fixed reporting deadline"}</dd>
              </div>
              {result.deadline ? (
                <>
                  <div>
                    <dt className="font-semibold">Latest date to report</dt>
                    <dd>{result.deadline}</dd>
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
            Choose the event and date, then work out the deadline.
          </p>
        )}
      </section>
    </div>
  );
}
