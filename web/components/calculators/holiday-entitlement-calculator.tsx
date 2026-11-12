"use client";

import { useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateHoliday,
  type HolidayInput,
  type HolidayMode,
  type HolidayResult,
} from "@/lib/calculators/holiday-entitlement-calculator";
import type { CalculatorPreset } from "@/lib/calculators/frame";

type Form = {
  mode: HolidayMode;
  daysPerWeek: string;
  hoursPerWeek: string;
  equalDays: "yes" | "no";
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
  equalDays: "yes",
  hoursWorked: "",
  leaveYearStart: "",
  leaveYearEnd: "",
  startDate: "",
  endDate: "",
};

function errorFor(form: Form): string {
  if (form.mode === "hours") {
    if (form.equalDays === "no")
      return "This calculator handles regular hours spread evenly over each working day. For days of different lengths, work out the entitlement from the actual pattern (5.6 weeks of the hours worked, capped at 28 days of leave) or ask ACAS.";
    return "Check your answers: enter hours per week and the days per week they are worked over (1–7). A working day cannot be longer than 24 hours.";
  }
  return "Check your answers: fill every field, days per week must be 1–7 and dates must be in order.";
}

/** Example scenarios: they only fill in the form; the user still calculates. */
export const holidayPresets: readonly CalculatorPreset<Partial<Form>>[] = [
  {
    id: "full-time",
    label: "Full time, 5 days a week",
    values: { mode: "days", daysPerWeek: "5" },
  },
  {
    id: "part-time",
    label: "Part time, 3 days a week",
    values: { mode: "days", daysPerWeek: "3" },
  },
  {
    id: "hours",
    label: "22.5 hours a week",
    values: { mode: "hours", hoursPerWeek: "22.5", daysPerWeek: "3" },
  },
  {
    id: "irregular",
    label: "Irregular hours, 120 hours worked",
    values: { mode: "irregular", hoursWorked: "120" },
  },
];

function toInput(form: Form): HolidayInput {
  switch (form.mode) {
    case "days":
      return { mode: "days", daysPerWeek: Number(form.daysPerWeek) };
    case "hours":
      return {
        mode: "hours",
        hoursPerWeek: Number(form.hoursPerWeek),
        daysPerWeek: Number(form.daysPerWeek),
        equalDays: form.equalDays === "yes",
      };
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
  const [attempted, setAttempted] = useState(false);
  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setAttempted(false);
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

  const { result, error: liveError } = (() => {
    let result: HolidayResult | null = null;
    let error: string | null = null;

    const calculated = calculateHoliday(toInput(form));
    result = calculated;
    error = calculated ? null : errorFor(form);
    return { result, error };
  })();
  const error = attempted || JSON.stringify(form) !== JSON.stringify(initial) ? liveError : null;

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          setAttempted(true);
        }}
      >
        <PresetChips
          presets={holidayPresets}
          onSelect={(preset) => {
            setForm({ ...initial, ...preset.values });
            setAttempted(false);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> Your worker
        </h2>
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
        {form.mode === "hours" ? field("hoursPerWeek", "Hours worked per week", "number") : null}
        {form.mode === "days" || form.mode === "part_year"
          ? field("daysPerWeek", "Days worked per week", "number")
          : null}
        {form.mode === "hours" ? (
          <>
            {field(
              "daysPerWeek",
              "Days those hours are worked over",
              "number",
              "Needed for the 28-day cap: 45 hours over 6 days is capped at 28 × 7.5 = 210 hours.",
            )}
            <Select
              label="Is every working day the same length?"
              value={form.equalDays}
              onChange={(event) => update("equalDays", event.target.value as Form["equalDays"])}
            >
              <option value="yes">Yes, the same hours each day</option>
              <option value="no">No, the days are different lengths</option>
            </Select>
          </>
        ) : null}
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
              setAttempted(false);
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
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        <h2 className="text-headline text-label mb-3">2. Live result</h2>
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
