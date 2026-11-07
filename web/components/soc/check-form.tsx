"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { NumberField } from "@/components/ui/number-field";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { todayIso } from "@/lib/ui/dates";

export type MatchBody = components["schemas"]["SocMatchIn"];
type Applicant = NonNullable<components["schemas"]["SocCheckIn"]["applicant"]>;
type Situation = NonNullable<Applicant["situation"]>;
type SalaryPer = components["schemas"]["SocCheckIn"]["salary_per"];
type Nation = components["schemas"]["SocCheckIn"]["work_nation"];
type Flag = Exclude<keyof Applicant, "situation">;

export const SITUATIONS: readonly [Situation, string][] = [
  ["outside_uk", "Outside the UK"],
  ["switching_graduate", "Switching from Graduate"],
  ["switching_student", "Switching from Student"],
  ["switching_other", "Switching from another route"],
  ["extending", "Extending my permission"],
  ["changing_employer", "Changing employer"],
];
export const NATIONS: readonly Nation[] = ["England", "Scotland", "Wales", "Northern Ireland"];
export const PER: readonly [SalaryPer, string][] = [
  ["year", "a year"],
  ["month", "a month"],
  ["week", "a week"],
  ["hour", "an hour"],
];
export const QUALIFIERS: readonly [Flag, string][] = [
  ["under_26", "Under 26 on the application date"],
  ["recent_uk_student_or_graduate", "UK student or graduate in the last 2 years"],
  ["professional_training", "Working towards a UK professional qualification"],
  ["postdoctoral", "In a listed postdoctoral role"],
  ["phd_relevant", "Holds a PhD relevant to the job"],
  ["stem_phd", "Holds a STEM PhD"],
  ["skilled_worker_before_2024_04_04", "Skilled Worker since before 4 April 2024, continuous"],
  ["skilled_worker_before_2025_07_22", "Skilled Worker since before 22 July 2025, continuous"],
  ["same_sponsor", "Same sponsor as my last permission"],
  ["previous_isl_same_job", "On the Immigration Salary List last time, same job and sponsor"],
];

export type FormState = {
  jobTitle: string;
  jobDescription: string;
  weeklyHours: number | null;
  offeredSalary: number | null;
  salaryPer: SalaryPer;
  workNation: Nation;
  cosDate: string;
  situation: Situation;
  flags: Partial<Record<Flag, boolean>>;
};

export function initialForm(): FormState {
  return {
    jobTitle: "",
    jobDescription: "",
    weeklyHours: 37.5,
    offeredSalary: null,
    salaryPer: "year",
    workNation: "England",
    cosDate: todayIso(),
    situation: "outside_uk",
    flags: {},
  };
}

/** The request body for match and save: every field the API takes, with flags left out when off. */
export function toBody(form: FormState): MatchBody {
  // The API takes every flag, so each one is sent, true or false.
  const flags = Object.fromEntries(
    QUALIFIERS.map(([flag]) => [flag, form.flags[flag] === true]),
  ) as Record<Flag, boolean>;
  const applicant: Applicant = { situation: form.situation, ...flags };
  return {
    job_title: form.jobTitle.trim(),
    job_description: form.jobDescription.trim(),
    check: {
      weekly_hours: form.weeklyHours ?? 0,
      offered_salary: form.offeredSalary ?? 0,
      salary_per: form.salaryPer,
      work_nation: form.workNation,
      cos_assignment_date: form.cosDate || null,
      applicant,
    },
  };
}

type Errors = Partial<Record<"jobTitle" | "weeklyHours" | "offeredSalary", string>>;

function validate(form: FormState): Errors {
  const errors: Errors = {};
  if (form.jobTitle.trim().length < 2) errors.jobTitle = "Enter the job title.";
  if (form.weeklyHours === null || form.weeklyHours <= 0 || form.weeklyHours > 168) {
    errors.weeklyHours = "Enter the hours a week, between 0 and 168.";
  }
  if (form.offeredSalary === null || form.offeredSalary < 0) {
    errors.offeredSalary = "Enter the offered salary.";
  }
  return errors;
}

type Props = {
  busy: boolean;
  canRun: boolean;
  onSubmit: (body: MatchBody) => void;
};

export function CheckForm({ busy, canRun, onSubmit }: Props) {
  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<Errors>({});

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length === 0) onSubmit(toBody(form));
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-5" aria-label="Job details">
      <TextField
        label="Job title"
        name="job_title"
        autoComplete="off"
        value={form.jobTitle}
        onChange={(event) => set("jobTitle", event.target.value)}
        error={errors.jobTitle}
        hint="For example: Adviser, sales, or Bricklayer"
      />
      <TextArea
        label="Job description (optional, but it improves the match)"
        name="job_description"
        rows={4}
        value={form.jobDescription}
        onChange={(event) => set("jobDescription", event.target.value)}
        maxLength={4000}
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <NumberField
          label="Hours a week"
          unit="hours"
          value={form.weeklyHours}
          onChange={(value) => set("weeklyHours", value)}
          error={errors.weeklyHours}
          min={0}
          max={168}
        />
        <NumberField
          label="Offered salary"
          unit="currency"
          value={form.offeredSalary}
          onChange={(value) => set("offeredSalary", value)}
          error={errors.offeredSalary}
          min={0}
        />
        <Select
          label="Salary is paid"
          value={form.salaryPer}
          onChange={(event) => set("salaryPer", event.target.value as SalaryPer)}
        >
          {PER.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <Select
          label="Work location"
          value={form.workNation}
          onChange={(event) => set("workNation", event.target.value as Nation)}
        >
          {NATIONS.map((nation) => (
            <option key={nation} value={nation}>
              {nation}
            </option>
          ))}
        </Select>
        <TextField
          label="Certificate of Sponsorship assignment date"
          type="date"
          value={form.cosDate}
          onChange={(event) => set("cosDate", event.target.value)}
          hint="Leave as today if you have not assigned the CoS yet"
        />
        <Select
          label="Your situation"
          value={form.situation}
          onChange={(event) => set("situation", event.target.value as Situation)}
        >
          {SITUATIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      <fieldset className="grid gap-3">
        <legend className="text-callout text-label-secondary">About the applicant</legend>
        {QUALIFIERS.map(([flag, label]) => (
          <Checkbox
            key={flag}
            label={label}
            checked={Boolean(form.flags[flag])}
            onCheckedChange={(checked) => set("flags", { ...form.flags, [flag]: checked === true })}
          />
        ))}
      </fieldset>
      <div>
        <Button type="submit" disabled={busy || !canRun}>
          {busy ? "Checking…" : "Check this job"}
        </Button>
        {canRun ? null : (
          <p className="text-footnote text-label-secondary mt-2">
            You can read saved checks, but not run a new one.
          </p>
        )}
      </div>
    </form>
  );
}
