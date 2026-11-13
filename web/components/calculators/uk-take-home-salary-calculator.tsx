"use client";

import { useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateTakeHome,
  niCategories,
  takeHomeYears,
  type TakeHomeInput,
  type LoanPlan,
  type PensionMethod,
  type Region,
  type TakeHomeResult,
} from "@/lib/calculators/uk-take-home-salary-calculator";

type Form = {
  taxYear: TakeHomeInput["taxYear"];
  region: Region;
  salary: string;
  taxCode: string;
  pensionMethod: PensionMethod;
  pensionPercent: string;
  studentLoan: LoanPlan;
  postgradLoan: boolean;
  niCategory: string;
  otherJobs: boolean;
  benefits: string;
  otherDeductions: string;
};

const initial: Form = {
  taxYear: "2026-2027",
  region: "england",
  salary: "",
  taxCode: "auto",
  pensionMethod: "none",
  pensionPercent: "",
  studentLoan: "none",
  postgradLoan: false,
  niCategory: "A",
  otherJobs: false,
  benefits: "",
  otherDeductions: "",
};

const money = (value: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);

const presets: readonly CalculatorPreset<Partial<Form>>[] = [
  { id: "standard", label: "\u00a335,000 standard salary", values: { salary: "35000" } },
  {
    id: "scottish",
    label: "\u00a345,000 in Scotland",
    values: { salary: "45000", region: "scotland" },
  },
];

export function UkTakeHomeSalaryCalculator() {
  const [form, setForm] = useState<Form>(initial);
  const [attempted, setAttempted] = useState(false);
  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setAttempted(false);
  }
  const num = (value: string) => (value.trim() === "" ? 0 : Number(value));
  const field = (
    key: "salary" | "pensionPercent" | "benefits" | "otherDeductions",
    label: string,
  ) => (
    <TextField
      label={label}
      type="number"
      clearable={false}
      value={form[key]}
      onChange={(event) => update(key, event.target.value)}
    />
  );

  const { result, error: liveError } = (() => {
    let result: TakeHomeResult | null = null;
    let error: string | null = null;

    const calculated = calculateTakeHome({
      taxYear: form.taxYear,
      region: form.region,
      salary: num(form.salary),
      taxCode: form.taxCode,
      pensionMethod: form.pensionMethod,
      pensionPercent: num(form.pensionPercent),
      studentLoan: form.studentLoan,
      postgradLoan: form.postgradLoan,
      niCategory: form.niCategory,
      otherJobs: form.otherJobs,
      benefits: num(form.benefits),
      otherDeductions: num(form.otherDeductions),
    });
    result = calculated;
    error = calculated
      ? null
      : form.taxYear === "2025-2026" && form.studentLoan === "plan 5"
        ? "Plan 5 repayments are not supported for 2025–2026. Choose another loan plan or the 2026–2027 tax year."
        : "Check your answers: enter a salary above zero, a supported tax code for your region (such as 1257L, BR, D0, SD1 or auto) and percentages from 0 to 100.";
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
          presets={presets}
          onSelect={(preset) => {
            setForm({ ...initial, ...preset.values });
            setAttempted(false);
          }}
        />
        <h2 className="text-title-2 text-label">1. Your pay</h2>
        <Select
          label="Tax year"
          value={form.taxYear}
          onChange={(event) => update("taxYear", event.target.value as Form["taxYear"])}
        >
          {Object.keys(takeHomeYears).map((year) => (
            <option key={year} value={year}>
              {year.replace("-", "–")}
            </option>
          ))}
        </Select>
        <Select
          label="Where do you live?"
          value={form.region}
          onChange={(event) => update("region", event.target.value as Region)}
        >
          <option value="england">England or Northern Ireland</option>
          <option value="scotland">Scotland</option>
          <option value="wales">Wales</option>
        </Select>
        {field("salary", "Annual salary (£)")}
        <TextField
          label="Tax code"
          hint="Type auto for the standard allowance. Scottish non-basic flat codes use SD0–SD3. S/C prefixes must match your region. Emergency codes are not supported."
          clearable={false}
          value={form.taxCode}
          onChange={(event) => update("taxCode", event.target.value)}
        />
        <Select
          label="National Insurance category"
          value={form.niCategory}
          onChange={(event) => update("niCategory", event.target.value)}
        >
          {niCategories.map((letter) => (
            <option key={letter} value={letter}>
              {letter}
            </option>
          ))}
        </Select>
        <Select
          label="Pension method"
          value={form.pensionMethod}
          onChange={(event) => update("pensionMethod", event.target.value as PensionMethod)}
        >
          <option value="none">No pension</option>
          <option value="net_pay">Net pay arrangement</option>
          <option value="salary_sacrifice">Salary sacrifice</option>
          <option value="relief_at_source">Relief at source</option>
        </Select>
        {form.pensionMethod !== "none" ? field("pensionPercent", "Pension contribution (%)") : null}
        <Select
          label="Student loan plan"
          value={form.studentLoan}
          onChange={(event) => update("studentLoan", event.target.value as LoanPlan)}
        >
          <option value="none">None</option>
          <option value="plan 1">Plan 1</option>
          <option value="plan 2">Plan 2</option>
          <option value="plan 4">Plan 4</option>
          <option value="plan 5">Plan 5</option>
        </Select>
        <label className="text-callout text-label flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.postgradLoan}
            onChange={(event) => update("postgradLoan", event.target.checked)}
          />
          Postgraduate loan
        </label>
        <label className="text-callout text-label flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.otherJobs}
            onChange={(event) => update("otherJobs", event.target.checked)}
          />
          I have another job that uses my tax-free allowance
        </label>
        {field("benefits", "Taxable benefits in kind per year (£)")}
        {field("otherDeductions", "Other deductions after tax per year (£)")}
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Calculate take-home</Button>
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
        aria-label="Take-home result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        <h2 className="text-headline text-label mb-3">2. Live result</h2>
        {result ? (
          <>
            <h2 className="text-title-2 text-label">Your take-home pay</h2>
            <p className="text-headline text-label mt-3">
              {money(result.annual)} a year · {money(result.monthly)} a month ·{" "}
              {money(result.weekly)} a week
            </p>
            <table className="text-callout text-label mt-4 w-full">
              <caption className="sr-only">Annual breakdown</caption>
              <thead>
                <tr>
                  <th scope="col" className="text-left">
                    Item
                  </th>
                  <th scope="col" className="text-right">
                    Per year
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row" className="text-left font-normal">
                      {row.label}
                    </th>
                    <td className="text-right">{money(row.annual)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-footnote text-label-secondary mt-3">
              Payroll source for {form.taxYear.replace("-", "–")}:{" "}
              <a className="underline" href={takeHomeYears[form.taxYear].source_url}>
                {takeHomeYears[form.taxYear].title}
              </a>
            </p>
            {result.notes.map((note) => (
              <p key={note} className="text-footnote text-label-secondary mt-3">
                {note}
              </p>
            ))}
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Enter your pay details to see your take-home estimate update as you edit.
          </p>
        )}
      </section>
    </div>
  );
}
