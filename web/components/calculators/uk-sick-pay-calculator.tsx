"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import { calculateSickPay, type SickPayInput } from "@/lib/calculators/uk-sick-pay-calculator";

const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const initial = {
  employeeStatus: "employee",
  startDate: "",
  endDate: "",
  weeklyEarnings: "",
  days: [1, 2, 3, 4, 5],
};
const gbp = (amount: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(amount);
export function SickPayCalculator() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<ReturnType<typeof calculateSickPay> | null>(null);
  const [error, setError] = useState<string | null>(null);
  function update<K extends keyof typeof initial>(key: K, value: (typeof initial)[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setResult(null);
    setError(null);
  }
  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        noValidate
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          setResult(null);
          try {
            if ([form.startDate, form.endDate, form.weeklyEarnings].some((v) => v.trim() === ""))
              throw new Error("Enter the start date, end date and average weekly earnings.");
            setResult(
              calculateSickPay({
                employeeStatus: form.employeeStatus,
                startDate: form.startDate,
                endDate: form.endDate,
                qualifyingDays: form.days,
                weeklyEarnings: Number(form.weeklyEarnings),
              } as SickPayInput),
            );
            setError(null);
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Check your answers.");
          }
        }}
      >
        <h2 className="text-title-2 text-label">Absence details</h2>
        <Select
          label="Worker status"
          value={form.employeeStatus}
          onChange={(event) => update("employeeStatus", event.target.value)}
        >
          <option value="employee">Employee</option>
          <option value="agency">Agency worker</option>
          <option value="other">Self-employed or other</option>
        </Select>
        <TextField
          label="First day of sickness"
          type="date"
          clearable={false}
          value={form.startDate}
          onChange={(event) => update("startDate", event.target.value)}
        />
        <TextField
          label="Last day of sickness"
          type="date"
          clearable={false}
          value={form.endDate}
          onChange={(event) => update("endDate", event.target.value)}
          hint="For an ongoing absence, enter the date you want to calculate to."
        />
        <TextField
          label="Average weekly earnings (£)"
          type="number"
          min="0"
          step="0.01"
          clearable={false}
          value={form.weeklyEarnings}
          onChange={(event) => update("weeklyEarnings", event.target.value)}
          hint="Average over the 8 weeks before the absence."
        />
        <fieldset className="space-y-2">
          <legend className="text-callout text-label">
            Qualifying days (days normally worked)
          </legend>
          {dayNames.map((name, index) => (
            <label key={name} className="text-callout text-label flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.days.includes(index)}
                onChange={(event) =>
                  update(
                    "days",
                    event.target.checked
                      ? [...form.days, index]
                      : form.days.filter((day) => day !== index),
                  )
                }
              />
              {name}
            </label>
          ))}
        </fieldset>
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Calculate sick pay</Button>
          <Button
            type="button"
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
        aria-label="Sick pay result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          result.eligible ? (
            <>
              <h2 className="text-title-2 text-label">Estimated Statutory Sick Pay</h2>
              <dl className="text-callout text-label mt-4 space-y-2">
                <Row label="Weekly rate" value={gbp(result.weeklyRate)} />
                <Row label="Daily rate" value={gbp(result.dailyRate)} />
                <Row label="Payable days" value={String(result.payableDays)} />
                <Row label="Total SSP" value={gbp(result.total)} />
              </dl>
              {result.maxReached ? (
                <p className="text-footnote text-label-secondary mt-3">
                  The 28-week maximum was reached; later days are not paid.
                </p>
              ) : null}
              <table className="text-footnote text-label mt-4 w-full">
                <caption className="sr-only">Week-by-week SSP</caption>
                <thead>
                  <tr>
                    <th scope="col" className="text-left">
                      Week
                    </th>
                    <th scope="col" className="text-left">
                      Dates
                    </th>
                    <th scope="col" className="text-right">
                      Days
                    </th>
                    <th scope="col" className="text-right">
                      SSP
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.weeks.map((week) => (
                    <tr key={week.week}>
                      <td>{week.week}</td>
                      <td>
                        {week.from} to {week.to}
                      </td>
                      <td className="text-right">{week.payableDays}</td>
                      <td className="text-right">{gbp(week.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p role="status" className="text-callout text-label">
              {result.reason}
            </p>
          )
        ) : (
          <p className="text-callout text-label-secondary">
            Enter the absence details to estimate SSP.
          </p>
        )}
        <p className="text-footnote text-label-secondary mt-5">
          For absences starting on or after 6 April 2026: SSP is paid from the first qualifying day
          with no waiting days and no lower earnings limit, at the lower of the weekly rate or 80%
          of average weekly earnings, for up to 28 weeks. Part days are not payable.
        </p>
        <p className="text-footnote text-label-secondary mt-3">
          Linked periods of sickness, SSP already paid, Statutory Maternity Pay, late notification
          and transitional rules are not applied. Check GOV.UK before paying.
        </p>
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
