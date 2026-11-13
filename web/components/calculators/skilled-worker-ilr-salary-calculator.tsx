"use client";

import { useMemo, useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import {
  calculateIlrSalary,
  FULL_TIME_HOURS,
  searchOccupations,
  type Occupation,
  type Situation,
} from "@/lib/calculators/skilled-worker-ilr-salary-calculator";

const gbp = (value: number) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value);

type Form = { query: string; situation: Situation; hours: string };

/** Example scenarios: they only fill in the form; every figure comes from the rates data. */
export const ilrSalaryPresets: readonly CalculatorPreset<Form>[] = [
  {
    id: "developer",
    label: "Software developer, full time",
    values: { query: "2134", situation: "standard", hours: String(FULL_TIME_HOURS) },
  },
  {
    id: "part-time",
    label: "Chief executive, 30 hours a week",
    values: { query: "1111", situation: "standard", hours: "30" },
  },
  {
    id: "transitional",
    label: "Developer, first certificate before April 2024",
    values: { query: "2134", situation: "transitional", hours: String(FULL_TIME_HOURS) },
  },
];

const INVALID = "Incomplete: search for your job, then enter weekly hours between 1 and 168.";

export function SkilledWorkerIlrSalaryCalculator() {
  const [query, setQuery] = useState("");
  const [code, setCode] = useState("");
  const [situation, setSituation] = useState<Situation>("standard");
  const [hours, setHours] = useState(String(FULL_TIME_HOURS));
  const [touched, setTouched] = useState(false);

  const matches = useMemo(() => searchOccupations(query), [query]);
  const chosen: Occupation | undefined = matches.find((o) => o.code === code) ?? matches[0];
  const h = Number(hours);
  const valid = chosen !== undefined && Number.isFinite(h) && h >= 1 && h <= 168;
  // Live result: recalculated locally on every change once the user has answered something.
  const input = touched && valid && chosen ? { occupation: chosen, situation, hours: h } : null;
  const result = input ? calculateIlrSalary(input) : null;
  const error = touched && !valid ? INVALID : null;
  const touch = () => setTouched(true);

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
        <PresetChips
          presets={ilrSalaryPresets}
          onSelect={(preset) => {
            setQuery(preset.values.query);
            setCode("");
            setSituation(preset.values.situation);
            setHours(preset.values.hours);
            setTouched(true);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> Your job
        </h2>
        <TextField
          label="Job title or SOC code"
          clearable={false}
          hint="For example “software” or 2134."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setCode("");
            touch();
          }}
        />
        {matches.length > 0 ? (
          <Select
            label="Matching occupation"
            value={chosen?.code ?? ""}
            onChange={(event) => {
              setCode(event.target.value);
              touch();
            }}
          >
            {matches.map((o) => (
              <option key={o.code} value={o.code}>
                {o.code} {o.title}
              </option>
            ))}
          </Select>
        ) : null}
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">2.</span> Your situation and hours
        </h2>
        <Select
          label="Your situation"
          value={situation}
          onChange={(event) => {
            setSituation(event.target.value as Situation);
            touch();
          }}
        >
          <option value="standard">Usual Skilled Worker</option>
          <option value="health_care">Health and Care Worker visa</option>
          <option value="salary_list">Job on the Immigration Salary List</option>
          <option value="transitional">First certificate of sponsorship before 4 April 2024</option>
          <option value="sportsperson">International Sportsperson</option>
        </Select>
        <TextField
          label="Weekly working hours"
          type="number"
          clearable={false}
          hint={`The hours your sponsor states; a full week is ${FULL_TIME_HOURS}.`}
          value={hours}
          onChange={(event) => {
            setHours(event.target.value);
            touch();
          }}
        />
        <div className="flex flex-wrap gap-3">
          <Button
            variant="gray"
            onClick={() => {
              setQuery("");
              setCode("");
              setSituation("standard");
              setHours(String(FULL_TIME_HOURS));
              setTouched(false);
            }}
          >
            Reset answers
          </Button>
        </div>
        {error ? (
          <p role="alert" className="text-callout text-label">
            {error}
          </p>
        ) : null}
      </form>
      <section
        aria-label="Salary result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        {result && input ? (
          <>
            <h2 className="text-title-2 text-label">Your settlement salary requirement</h2>
            <p className="text-callout text-label-secondary mt-2">
              {input.occupation.code} {input.occupation.title} · {result.basis}
            </p>
            <p className="text-headline text-label mt-4">
              {result.status === "review"
                ? "We can’t give a figure for this situation"
                : result.required === null
                  ? "Depends on your pay scale"
                  : `At least ${gbp(result.required)} a year`}
            </p>
            {result.status === "review" ? null : (
              <dl className="text-callout text-label mt-3 space-y-1">
                {result.floor !== null ? (
                  <Row label="Fixed minimum" value={gbp(result.floor)} />
                ) : null}
                {result.fullTimeGoingRate !== null ? (
                  <Row
                    label={`Going rate (${FULL_TIME_HOURS} hours)`}
                    value={gbp(result.fullTimeGoingRate)}
                  />
                ) : null}
                {result.goingRate !== null ? (
                  <Row
                    label={`Going rate for ${result.hours} hours`}
                    value={gbp(result.goingRate)}
                  />
                ) : null}
              </dl>
            )}
            <ul className="text-footnote text-label-secondary mt-4 list-disc space-y-1 pl-5">
              {result.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
            <p className="text-footnote text-label-secondary mt-3">
              This is guidance, not legal advice. Check the current rules before you apply.
            </p>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Search for your job or pick an example; the salary you need to settle updates as you go.
          </p>
        )}
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
