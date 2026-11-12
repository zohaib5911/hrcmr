"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateEmployerCost,
  defaultEmployerPensionRate,
  employerCostYears,
  type EmployerCostInput,
} from "@/lib/calculators/uk-employer-cost-calculator";

const initial = {
  taxYear: "2026-2027",
  salary: "",
  age: "",
  employeeType: "standard",
  pensionRate: String(defaultEmployerPensionRate),
  pensionBasis: "qualifying",
};
const gbp = (amount: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(amount);
export function EmployerCostCalculator() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<ReturnType<typeof calculateEmployerCost> | null>(null);
  const [error, setError] = useState<string | null>(null);
  function update(key: keyof typeof initial, value: string) {
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
            if ([form.salary, form.age, form.pensionRate].some((value) => value.trim() === ""))
              throw new Error("Enter salary, age and pension percentage.");
            setResult(
              calculateEmployerCost({
                ...form,
                salary: Number(form.salary),
                age: Number(form.age),
                pensionRate: Number(form.pensionRate),
              } as EmployerCostInput),
            );
            setError(null);
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Check your answers.");
          }
        }}
      >
        <h2 className="text-title-2 text-label">Employee details</h2>
        <Select
          label="Tax year"
          value={form.taxYear}
          onChange={(event) => update("taxYear", event.target.value)}
        >
          {Object.keys(employerCostYears).map((year) => (
            <option key={year} value={year}>
              {year.replace("-", "–")}
            </option>
          ))}
        </Select>
        <TextField
          label="Annual gross salary (£)"
          type="number"
          min="0"
          step="0.01"
          clearable={false}
          value={form.salary}
          onChange={(event) => update("salary", event.target.value)}
        />
        <TextField
          label="Age in whole years"
          type="number"
          min="0"
          step="1"
          clearable={false}
          value={form.age}
          onChange={(event) => update("age", event.target.value)}
        />
        <Select
          label="Employee type"
          value={form.employeeType}
          onChange={(event) => update("employeeType", event.target.value)}
          hint="Choose apprentice only for a recognised apprenticeship eligible for HMRC category H relief."
        >
          <option value="standard">Standard employee</option>
          <option value="apprentice">Recognised apprentice</option>
        </Select>
        <TextField
          label="Employer pension contribution (%)"
          type="number"
          min="0"
          max="100"
          step="any"
          clearable={false}
          value={form.pensionRate}
          onChange={(event) => update("pensionRate", event.target.value)}
          hint="Use the rate agreed with your scheme. Enter 0 only if no employer contribution applies; this tool does not determine pension eligibility."
        />
        <Select
          label="Pension earnings basis"
          value={form.pensionBasis}
          onChange={(event) => update("pensionBasis", event.target.value)}
        >
          <option value="qualifying">Qualifying earnings</option>
          <option value="full">Full salary</option>
        </Select>
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Calculate employer cost</Button>
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
        aria-label="Employer cost result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">Estimated annual employer cost</h2>
            <dl className="text-callout text-label mt-4 space-y-2">
              <Row label="Gross salary" amount={Number(form.salary)} />
              <Row label="Employer National Insurance" amount={result.employerNI} />
              <Row label="Employer pension" amount={result.employerPension} />
              <Row label="Total annual cost before allowances and Levy" amount={result.totalCost} />
            </dl>
            <p className="text-footnote text-label-secondary mt-4">
              NI category {result.category}: {gbp(result.niEarnings)} above the annual threshold of{" "}
              {gbp(result.niThreshold)} × {result.niRate * 100}%. Pension:{" "}
              {gbp(result.pensionableEarnings)} × {form.pensionRate}%.
            </p>
            <h3 className="text-headline text-label mt-5">Apprenticeship Levy</h3>
            <p className="text-footnote text-label-secondary mt-2">
              The Levy is {result.levyRate * 100}% of the employer’s annual pay bill, with an annual
              allowance of {gbp(result.levyAllowance)}. A pay bill over{" "}
              {gbp(result.levyPayBillThreshold)} may trigger payment. Connected employers share the
              allowance. It is assessed across the employer and is excluded from this employee’s
              total.
            </p>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Enter the employee details to estimate annual cost.
          </p>
        )}
        <p className="text-footnote text-label-secondary mt-5">
          This is a full-year budget estimate with unchanged salary, age and NI status. Payroll uses
          pay-period thresholds and rounding; birthdays and changes during the year can alter the
          result. Employer NI can still apply after State Pension age.
        </p>
        <p className="text-footnote text-label-secondary mt-3">
          Employment Allowance is employer-wide and has not been deducted. Veteran, Freeport and
          Investment Zone relief, salary sacrifice, benefits, bonuses and other employment costs are
          outside this estimate.
        </p>
        <p className="text-footnote text-label-secondary mt-3">
          Pension uses your chosen contribution and basis, using the qualifying earnings band in the
          pension source checked on 12 November 2026. Confirm your scheme’s rules for the selected
          year; age does not decide pension enrolment here.
        </p>
      </section>
    </div>
  );
}
function Row({ label, amount }: { label: string; amount: number }) {
  return (
    <div className="flex justify-between gap-4">
      <dt>{label}</dt>
      <dd>{gbp(amount)}</dd>
    </div>
  );
}
