"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  calculateRedundancy,
  type RedundancyInput,
} from "@/lib/calculators/uk-redundancy-pay-calculator";

const initial = {
  jurisdiction: "GB",
  dateOfBirth: "",
  startDate: "",
  redundancyDate: "",
  weeklyPay: "",
  status: "employee",
  reason: "redundancy",
};
const money = (value: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);

export function RedundancyPayCalculator() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<ReturnType<typeof calculateRedundancy> | null>(null);
  const [error, setError] = useState<string | null>(null);
  function update(key: keyof typeof initial, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setResult(null);
    setError(null);
  }
  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          setResult(null);
          try {
            if (!form.weeklyPay.trim()) throw new Error("Enter your average gross weekly pay.");
            setResult(
              calculateRedundancy({
                ...form,
                weeklyPay: Number(form.weeklyPay),
              } as RedundancyInput),
            );
            setError(null);
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Check your answers.");
          }
        }}
      >
        <h2 className="text-title-2 text-label">Your employment</h2>
        <Select
          label="Jurisdiction"
          value={form.jurisdiction}
          onChange={(event) => update("jurisdiction", event.target.value)}
        >
          <option value="GB">Great Britain (England, Scotland, Wales)</option>
          <option value="NI">Northern Ireland</option>
        </Select>
        {(
          [
            ["dateOfBirth", "Date of birth"],
            ["startDate", "Continuous employment start date"],
            ["redundancyDate", "Redundancy relevant date"],
          ] as const
        ).map(([key, label]) => (
          <TextField
            key={key}
            label={label}
            type="date"
            clearable={false}
            value={form[key]}
            onChange={(event) => update(key, event.target.value)}
          />
        ))}
        <p className="text-footnote text-label-secondary">
          Usually the relevant date is the end of your notice period. With pay in lieu, shortened
          notice or a trial in another role, confirm the correct date with an adviser; it may be
          later than your last working day. Rates cover 6 April 2026 to 5 April 2027.
        </p>
        <TextField
          label="Average gross weekly pay (£)"
          type="number"
          step="0.01"
          min="0"
          clearable={false}
          value={form.weeklyPay}
          onChange={(event) => update("weeklyPay", event.target.value)}
          hint="Use the appropriate 12-week average before notice, including applicable regular overtime, bonuses and commission. Use normal pay for furlough periods. For variable or unusual pay, check the source guidance."
        />
        <Select
          label="Employment status"
          value={form.status}
          onChange={(event) => update("status", event.target.value)}
        >
          <option value="employee">Employee</option>
          <option value="other">Worker or self-employed</option>
          <option value="unsure">Unsure or special category</option>
        </Select>
        <Select
          label="Reason for leaving"
          value={form.reason}
          onChange={(event) => update("reason", event.target.value)}
        >
          <option value="redundancy">
            Redundancy (including a non-renewed fixed term because of redundancy)
          </option>
          <option value="misconduct">Dismissal for misconduct</option>
          <option value="alternative">
            Kept on, or suitable alternative work refused without good reason
          </option>
          <option value="other">Other reason or unsure</option>
        </Select>
        <p className="text-footnote text-label-secondary">
          This estimates the statutory minimum for ordinary employees with continuous service.
          Special categories (including armed forces, police, Crown servants, certain apprentices,
          dock workers and share fishermen), lay-offs, disputed continuity or early departure need
          individual review. Choose “Unsure or special category” if these apply.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button type="submit">Calculate redundancy pay</Button>
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
        aria-label="Redundancy result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">
              {result.eligible ? "Estimated statutory redundancy pay" : "Check eligibility"}
            </h2>
            {result.total !== null ? (
              <>
                <p className="text-title-1 text-label mt-3">{money(result.total)}</p>
                <dl className="text-callout text-label mt-4 space-y-2">
                  <div>
                    <dt>Completed continuous service</dt>
                    <dd>{result.serviceYears} years</dd>
                  </div>
                  <div>
                    <dt>Most recent full years counted</dt>
                    <dd>{result.countedYears} years</dd>
                  </div>
                  <div>
                    <dt>Weekly pay used</dt>
                    <dd>
                      {money(result.weeklyPay)} (cap: {money(result.cap)})
                    </dd>
                  </div>
                </dl>
                <table className="text-footnote text-label mt-5 w-full text-left">
                  <caption className="text-headline mb-2 text-left">
                    Age during each full year of service
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Age band</th>
                      <th scope="col">Years</th>
                      <th scope="col">Weeks per year</th>
                      <th scope="col">Weeks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.bands.map((band, index) => (
                      <tr key={index}>
                        <th scope="row">
                          {index === 0 ? "Under 22" : index === 1 ? "22–40" : "41 and over"}
                        </th>
                        <td>{band.years}</td>
                        <td>{band.weeks_per_year}</td>
                        <td>{band.weeks}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-callout text-label mt-4">
                  {result.weeks} weeks × {money(result.weeklyPay)} = {money(result.total)}
                </p>
              </>
            ) : (
              <p className="text-callout text-label mt-3">{result.message}</p>
            )}
            <p className="text-footnote text-label-secondary mt-5">
              Your contract may provide more. Notice pay, holiday pay and other final payments are
              separate. Confirm eligibility and the relevant date with your employer or an adviser.
            </p>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Enter your details to estimate statutory redundancy pay and see the workings.
          </p>
        )}
      </section>
    </div>
  );
}
