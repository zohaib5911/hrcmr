"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateHoliday,
  type HolidayInput,
  type HolidayMode,
  type HolidayResult,
} from "@/lib/calculators/holiday-entitlement-calculator";

type Form = {
  mode: HolidayMode;
  daysPerWeek: string;
  hoursPerWeek: string;
  hoursWorked: string;
  leaveYearStart: string;
  leaveYearEnd: string;
  startDate: string;
  endDate: string;
};

const initial: Form = {
  mode: "days",
  daysPerWeek: "",
  hoursPerWeek: "",
  hoursWorked: "",
  leaveYearStart: "",
  leaveYearEnd: "",
  startDate: "",
  endDate: "",
};

function toInput(form: Form): HolidayInput {
  switch (form.mode) {
    case "days":
      return { mode: "days", daysPerWeek: Number(form.daysPerWeek) };
    case "hours":
      return { mode: "hours", hoursPerWeek: Number(form.hoursPerWeek) };
    case "irregular":
      return { mode: "irregular", hoursWorked: Number(form.hoursWorked) };
    case "part_year":
      return {
        mode: "part_year",
        daysPerWeek: Number(form.daysPerWeek),
        leaveYearStart: form.leaveYearStart,
        leaveYearEnd: form.leaveYearEnd,
        startDate: form.startDate,
        endDate: form.endDate,
      };
  }
}

export function HolidayEntitlementCalculator() {
  const [form, setForm] = useState<Form>(initial);
  const [result, setResult] = useState<HolidayResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setResult(null);
    setError(null);
  }
  const field = (key: keyof Form, label: string, type: "number" | "date", hint?: string) => (
    <TextField
      label={label}
      type={type}
      clearable={false}
      {...(hint ? { hint } : {})}
      value={form[key]}
      onChange={(event) => update(key, event.target.value as never)}
    />
  );

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          const calculated = calculateHoliday(toInput(form));
          setResult(calculated);
          setError(
            calculated
              ? null
              : "Check your answers: fill every field, days per week must be 1–7 and dates must be in order.",
          );
        }}
      >
        <h2 className="text-title-2 text-label">Your worker</h2>
        <Select
          label="How do they work?"
          value={form.mode}
          onChange={(event) => update("mode", event.target.value as HolidayMode)}
        >
          <option value="days">Regular days per week, whole year</option>
          <option value="hours">Regular hours per week, whole year</option>
          <option value="part_year">Starts or leaves part way through the leave year</option>
          <option value="irregular">Irregular hours or part-year (accrual at 12.07%)</option>
        </Select>
        {form.mode === "days" || form.mode === "part_year"
          ? field("daysPerWeek", "Days worked per week", "number")
          : null}
        {form.mode === "hours" ? field("hoursPerWeek", "Hours worked per week", "number") : null}
        {form.mode === "irregular"
          ? field("hoursWorked", "Hours worked in the pay period", "number")
          : null}
        {form.mode === "part_year" ? (
          <>
            {field("leaveYearStart", "Leave year start", "date")}
            {field("leaveYearEnd", "Leave year end", "date")}
            {field("startDate", "First day in the job (or leave year start)", "date")}
            {field("endDate", "Last day in the job (or leave year end)", "date")}
          </>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Calculate holiday</Button>
          <Button
            variant="gray"
            onClick={() => {
              setForm(initial);
              setResult(null);
              setError(null);
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
        aria-label="Holiday result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-fill-secondary rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">Your holiday entitlement</h2>
            <p className="text-headline text-label mt-3">
              {result.entitlement} {result.unit}
            </p>
            <h3 className="text-headline text-label mt-4">Workings</h3>
            <ul className="text-callout text-label mt-2 list-disc space-y-1 pl-5">
              {result.workings.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="text-footnote text-label-secondary mt-3">
              This is the statutory minimum for Great Britain. Bank holidays may be included in it.
              Check the contract for any extra leave.
            </p>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Answer the questions, then calculate the holiday entitlement.
          </p>
        )}
      </section>
    </div>
  );
}
