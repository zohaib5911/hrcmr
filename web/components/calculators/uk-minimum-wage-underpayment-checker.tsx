"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  checkMinimumWage,
  wagePeriods,
  type WageInput,
} from "@/lib/calculators/uk-minimum-wage-underpayment-checker";
const initial = {
  payType: "time",
  frequency: "weekly",
  periodStart: "",
  age: "",
  apprentice: "no",
  hours: "",
  pay: "",
  workCosts: "0",
  sacrifice: "0",
  tips: "0",
  excludedPay: "0",
  accommodationDays: "0",
  accommodationCharge: "0",
};
const fields = {
  age: "Age at pay-period start",
  hours: "Minimum-wage hours for this period",
  pay: "Gross period pay before the reductions below (£)",
  workCosts: "Unreimbursed work costs and reducing deductions (£)",
  sacrifice: "Salary sacrificed, included in gross pay above (£)",
  tips: "Tips included in gross pay above (£)",
  excludedPay: "Other excluded pay included above (£)",
  accommodationDays: "Days employer accommodation provided",
  accommodationCharge: "Total accommodation charge for those days (£)",
};
const gbp = (n: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(n);
export function MinimumWageChecker() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<ReturnType<typeof checkMinimumWage> | null>(null);
  const [error, setError] = useState("");
  function update(key: keyof typeof initial, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    setResult(null);
    setError("");
  }
  return (
    <div className="space-y-6">
      <p className="text-callout text-label-secondary">
        Check one pay reference period, at most one calendar month. Use age and apprenticeship
        status at its start. Increases apply from the first period starting on or after the change.
        Confirm minimum-wage eligibility and school-leaving age separately.
      </p>
      <form
        noValidate
        className="grid gap-5 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          setResult(null);
          try {
            if (Object.values(form).some((v) => v.trim() === ""))
              throw new Error("Complete all fields; enter 0 where no amount applies.");
            const numeric = Object.fromEntries(
              Object.keys(fields).map((k) => [k, Number(form[k as keyof typeof fields])]),
            );
            setResult(
              checkMinimumWage({
                ...form,
                ...numeric,
                apprentice: form.apprentice !== "no",
                firstYear: form.apprentice === "first",
              } as unknown as WageInput),
            );
            setError("");
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Check your answers.");
          }
        }}
      >
        <Select
          label="Pay type"
          value={form.payType}
          onChange={(e) => update("payType", e.target.value)}
        >
          <option value="time">Time work</option>
          <option value="salary">Salaried hours</option>
          <option value="output">Output work</option>
          <option value="unmeasured">Unmeasured work</option>
        </Select>
        <Select
          label="Pay frequency"
          value={form.frequency}
          onChange={(e) => update("frequency", e.target.value)}
        >
          {["weekly", "fortnightly", "four-weekly", "monthly"].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </Select>
        <TextField
          label="Pay-period start"
          type="date"
          clearable={false}
          value={form.periodStart}
          onChange={(e) => update("periodStart", e.target.value)}
        />
        <Select
          label="Apprenticeship status at period start"
          value={form.apprentice}
          onChange={(e) => update("apprentice", e.target.value)}
        >
          <option value="no">Not an apprentice</option>
          <option value="first">Apprentice in first year</option>
          <option value="later">Apprentice after first year</option>
        </Select>
        {Object.entries(fields).map(([key, label]) => (
          <TextField
            key={key}
            label={label}
            type="number"
            min="0"
            step="any"
            clearable={false}
            value={form[key as keyof typeof fields]}
            onChange={(e) => update(key as keyof typeof fields, e.target.value)}
          />
        ))}
        <div className="flex gap-3">
          <Button type="submit">Check minimum wage</Button>
          <Button
            type="button"
            variant="gray"
            onClick={() => {
              setForm(initial);
              setResult(null);
              setError("");
            }}
          >
            Reset answers
          </Button>
        </div>
        {error ? <p role="alert">{error}</p> : null}
      </form>
      <p className="text-footnote text-label-secondary">
        Enter pay and hours allocated under minimum-wage rules, not annual salary or take-home pay.
        Do not subtract tax or National Insurance. Enter each reduction once: if pay is already
        after salary sacrifice, enter 0 for sacrifice. Exclude tips only if included above. Other
        excluded pay includes expense reimbursements, allowances and (for time/output work) overtime
        or shift premiums above basic pay. Work costs include required uniforms and tools; check the
        guidance for exceptions.
      </p>
      <p className="text-footnote text-label-secondary">
        Time work includes qualifying training and travel between assignments. For salaried hours
        use the statutory basic-hours allocation and any excess hours; output work requires the
        applicable actual or rated-output hours, and unmeasured work requires actual hours or a
        valid daily average agreement. This tool does not derive those hours. Review the official
        calculation guidance for bonuses, deferred pay and complex arrangements.
      </p>
      <section
        aria-label="Minimum wage result"
        aria-live="polite"
        className="rounded-control bg-fill-secondary p-5"
      >
        {result ? (
          <>
            <h2 className="text-title-2">
              {result.belowMinimum ? "Potential underpayment" : "No shortfall on these inputs"}
            </h2>
            <p>
              Effective hourly rate: {gbp(result.hourlyRate)}. Minimum: {gbp(result.rate)} (
              {result.band}).
            </p>
            <p>
              Counted pay: {gbp(result.countedPay)}. Accommodation adjustment:{" "}
              {gbp(result.adjustment)}.
            </p>
            <p>Period shortfall: {gbp(result.shortfall)}.</p>
            <p>
              Rate period: {result.period.valid_from} to {result.period.valid_to} (
              {result.period.status}). Comparison uses the unrounded hourly rate. Shortfall is
              rounded up to a penny; historical arrears enforcement may require a different
              calculation.
            </p>
          </>
        ) : (
          <p>Enter details to check this period.</p>
        )}
      </section>
      <h2 className="text-title-2">Current and historical hourly rates</h2>
      <div className="overflow-x-auto">
        <table className="text-footnote w-full text-left">
          <thead>
            <tr>
              <th scope="col">Period</th>
              <th scope="col">Age bands and hourly rates</th>
            </tr>
          </thead>
          <tbody>
            {wagePeriods.map((p) => (
              <tr key={p.valid_from}>
                <th scope="row">
                  {p.valid_from} – {p.valid_to} ({p.status})
                </th>
                <td>
                  {Object.entries(p.age_band_rates)
                    .filter(([, r]) => r !== undefined)
                    .map(([b, r]) => `${b}: ${gbp(r!)}`)
                    .join("; ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
