"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateIlrSalary,
  searchOccupations,
  type Occupation,
  type SalaryInput,
  type Situation,
} from "@/lib/calculators/skilled-worker-ilr-salary-calculator";

const gbp = (value: number) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value);

export function SkilledWorkerIlrSalaryCalculator() {
  const [query, setQuery] = useState("");
  const [code, setCode] = useState("");
  const [situation, setSituation] = useState<Situation>("standard");
  const [hours, setHours] = useState("37.5");
  const [input, setInput] = useState<SalaryInput | null>(null);
  const [error, setError] = useState<string | null>(null);

  const matches = searchOccupations(query);
  const chosen: Occupation | undefined = matches.find((o) => o.code === code) ?? matches[0];
  const reset = () => {
    setInput(null);
    setError(null);
  };
  const result = input ? calculateIlrSalary(input) : null;

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          const h = Number(hours);
          if (!chosen || !Number.isFinite(h) || h < 1 || h > 168) {
            setInput(null);
            setError("Search for your job, then enter weekly hours between 1 and 168.");
            return;
          }
          setError(null);
          setInput({ occupation: chosen, situation, hours: h });
        }}
      >
        <h2 className="text-title-2 text-label">Your job</h2>
        <TextField
          label="Job title or SOC code"
          clearable={false}
          hint="For example “software” or 2134."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setCode("");
            reset();
          }}
        />
        {matches.length > 0 ? (
          <Select
            label="Matching occupation"
            value={chosen?.code ?? ""}
            onChange={(event) => {
              setCode(event.target.value);
              reset();
            }}
          >
            {matches.map((o) => (
              <option key={o.code} value={o.code}>
                {o.code} {o.title}
              </option>
            ))}
          </Select>
        ) : null}
        <Select
          label="Your situation"
          value={situation}
          onChange={(event) => {
            setSituation(event.target.value as Situation);
            reset();
          }}
        >
          <option value="standard">Usual Skilled Worker or Health and Care Worker</option>
          <option value="salary_list">Job on the Immigration Salary List</option>
          <option value="transitional">First certificate of sponsorship before 4 April 2024</option>
          <option value="sportsperson">International Sportsperson</option>
        </Select>
        <TextField
          label="Weekly working hours"
          type="number"
          clearable={false}
          hint="The hours your sponsor states; a full week is 37.5."
          value={hours}
          onChange={(event) => {
            setHours(event.target.value);
            reset();
          }}
        />
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Calculate salary</Button>
          <Button
            variant="gray"
            onClick={() => {
              setQuery("");
              setCode("");
              setSituation("standard");
              setHours("37.5");
              reset();
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
        className="bg-bg-elevated rounded-control p-5 sm:p-6"
      >
        {result && input ? (
          <>
            <h2 className="text-title-2 text-label">Your settlement salary requirement</h2>
            <p className="text-callout text-label-secondary mt-2">
              {input.occupation.code} {input.occupation.title} · {result.basis}
            </p>
            <p className="text-headline text-label mt-4">
              {result.required === null
                ? "Depends on your pay scale"
                : `At least ${gbp(result.required)} a year`}
            </p>
            <dl className="text-callout text-label mt-3 space-y-1">
              {result.floor !== null ? (
                <Row label="Fixed minimum" value={gbp(result.floor)} />
              ) : null}
              {result.fullTimeGoingRate !== null ? (
                <Row label="Going rate (37.5 hours)" value={gbp(result.fullTimeGoingRate)} />
              ) : null}
              {result.goingRate !== null ? (
                <Row label={`Going rate for ${result.hours} hours`} value={gbp(result.goingRate)} />
              ) : null}
            </dl>
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
            Search for your job, then calculate the salary you need to settle.
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
