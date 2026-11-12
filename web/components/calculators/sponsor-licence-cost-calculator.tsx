"use client";

import { useMemo, useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import {
  calculateSponsorCosts,
  compareCertificateLengths,
  type Basis,
  type LicenceType,
  type Route,
  type SponsorCostInput,
  type Speed,
} from "@/lib/calculators/sponsor-licence-cost-calculator";

type Form = Record<
  | "turnover"
  | "assets"
  | "employees"
  | "months"
  | "soc"
  | "workers"
  | "adultDependants"
  | "childDependants",
  string
> & {
  licenceType: LicenceType;
  charity: "yes" | "no";
  route: Route;
  location: "outside" | "inside";
  speed: Speed;
  licencePriority: "yes" | "no";
  basis: Basis;
  gpTraining: "" | "yes" | "no";
};

const initial: Form = {
  licenceType: "new",
  charity: "no",
  turnover: "",
  assets: "",
  employees: "",
  route: "skilled_worker",
  location: "outside",
  months: "36",
  soc: "",
  workers: "1",
  adultDependants: "0",
  childDependants: "0",
  speed: "standard",
  licencePriority: "no",
  basis: "standard",
  gpTraining: "",
};

/** Example scenarios: they only fill in the form; every amount comes from the rates data. */
export const sponsorCostPresets: readonly CalculatorPreset<Partial<Form>>[] = [
  {
    id: "small",
    label: "Small company, 1 worker for 3 years",
    values: { turnover: "2000000", assets: "1000000", employees: "20", months: "36" },
  },
  {
    id: "large-family",
    label: "Large company, 2 workers with families for 5 years",
    values: {
      turnover: "50000000",
      assets: "20000000",
      employees: "400",
      months: "60",
      workers: "2",
      adultDependants: "1",
      childDependants: "2",
    },
  },
  {
    id: "charity-care",
    label: "Charity, Health and Care worker already in the UK",
    values: { charity: "yes", route: "health_care", location: "inside", months: "36" },
  },
];

const INVALID =
  "Check your answers: numbers cannot be negative, workers must be at least 1 and the certificate length 1–60 whole months. For SOC 2211, confirm GP specialty training.";

const gbp = (value: number) =>
  new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);
const num = (value: string) => (value.trim() === "" ? 0 : Number(value));

function toInput(form: Form): SponsorCostInput | null {
  const fields = [form.turnover, form.assets, form.employees, form.months, form.workers];
  const all = [...fields, form.adultDependants, form.childDependants].map(num);
  if (all.some((value) => !Number.isFinite(value) || value < 0)) return null;
  if (form.soc.trim() === "2211" && form.gpTraining === "") return null;
  const months = num(form.months);
  if (!Number.isInteger(months) || months < 1 || months > 60 || num(form.workers) < 1) return null;
  return {
    licenceType: form.licenceType,
    charity: form.charity === "yes",
    turnover: num(form.turnover),
    assets: num(form.assets),
    employees: num(form.employees),
    route: form.route,
    insideUK: form.location === "inside",
    months,
    soc: form.soc,
    gpTraining: form.soc.trim() === "2211" && form.gpTraining === "yes",
    workers: num(form.workers),
    adultDependants: num(form.adultDependants),
    childDependants: num(form.childDependants),
    speed: form.speed,
    licencePriority: form.licencePriority === "yes",
    basis: form.basis,
  };
}

export function SponsorLicenceCostCalculator() {
  const [form, setForm] = useState<Form>(initial);
  const [touched, setTouched] = useState(false);
  // Live result: recalculated locally on every change once the user has answered something.
  const input = useMemo(() => (touched ? toInput(form) : null), [form, touched]);
  const result = useMemo(() => (input ? calculateSponsorCosts(input) : null), [input]);
  const error = touched && !input ? INVALID : null;
  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setTouched(true);
  }
  const num_ = (key: keyof Form, label: string, hint?: string) => (
    <TextField
      label={label}
      type="number"
      clearable={false}
      {...(hint ? { hint } : {})}
      value={form[key]}
      onChange={(event) => update(key, event.target.value as never)}
    />
  );

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
        <PresetChips
          presets={sponsorCostPresets}
          onSelect={(preset) => {
            setForm({ ...initial, ...preset.values });
            setTouched(true);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> Your organisation
        </h2>
        <Select
          label="Licence application"
          value={form.licenceType}
          onChange={(event) => update("licenceType", event.target.value as LicenceType)}
        >
          <option value="new">New Worker licence</option>
          <option value="add_worker">
            Add a Worker licence to an existing Temporary Worker licence
          </option>
        </Select>
        <Select
          label="Registered charity or equivalent?"
          value={form.charity}
          onChange={(event) => update("charity", event.target.value as "yes" | "no")}
        >
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </Select>
        {form.charity === "no" ? (
          <>
            {num_(
              "turnover",
              "Annual turnover (£)",
              "Small if at least 2 of: turnover £15m or less, assets £7.5m or less, 50 employees or fewer.",
            )}
            {num_("assets", "Total assets (£)")}
            {num_("employees", "Employees")}
          </>
        ) : null}
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">2.</span> The role and certificate
        </h2>
        <Select
          label="Route"
          value={form.route}
          onChange={(event) => update("route", event.target.value as Route)}
        >
          <option value="skilled_worker">Skilled Worker</option>
          <option value="health_care">Health and Care Worker</option>
        </Select>
        <Select
          label="Where is the worker applying from?"
          value={form.location}
          onChange={(event) => update("location", event.target.value as "outside" | "inside")}
        >
          <option value="outside">Outside the UK</option>
          <option value="inside">Inside the UK</option>
        </Select>
        {num_("months", "Certificate length (months, 1–60)")}
        <div>
          <input
            aria-label="Certificate length slider"
            type="range"
            min={1}
            max={60}
            value={Math.min(60, Math.max(1, num(form.months) || 1))}
            onChange={(event) => update("months", event.target.value)}
            className="w-full"
          />
        </div>
        <TextField
          label="Occupation (SOC) code"
          clearable={false}
          hint="Four digits, used for skills-charge exemptions and the GP training visa extension."
          value={form.soc}
          onChange={(event) => update("soc", event.target.value)}
        />
        {form.soc.trim() === "2211" ? (
          <Select
            label="Is this GP specialty training?"
            value={form.gpTraining}
            onChange={(event) => update("gpTraining", event.target.value as Form["gpTraining"])}
          >
            <option value="">Select an answer</option>
            <option value="no">No</option>
            <option value="yes">Yes</option>
          </Select>
        ) : null}
        <p className="text-footnote text-label-secondary">
          The visa normally ends 14 days after the CoS employment end date (SW 18.1). Confirmed GP
          specialty training under SOC 2211 adds 4 months instead (SW 18.1A). IHS uses this longer
          visa period; ISC and visa fee tiers use the CoS employment length.
        </p>
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">3.</span> Workers, dependants and fees
        </h2>
        {num_("workers", "Number of workers")}
        {num_("adultDependants", "Adult dependants (18+) per worker")}
        {num_("childDependants", "Child dependants (under 18) per worker")}
        <Select
          label="Visa fee basis"
          value={form.basis}
          onChange={(event) => update("basis", event.target.value as Basis)}
        >
          <option value="standard">Standard fee</option>
          <option value="salary_list">Job on the immigration salary list</option>
        </Select>
        <Select
          label="Visa decision speed"
          value={form.speed}
          onChange={(event) => update("speed", event.target.value as Speed)}
        >
          <option value="standard">Standard</option>
          <option value="priority">Priority service</option>
          <option value="super_priority">Super priority service</option>
        </Select>
        <Select
          label="Pay for a faster licence decision?"
          value={form.licencePriority}
          onChange={(event) => update("licencePriority", event.target.value as "yes" | "no")}
        >
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </Select>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="gray"
            onClick={() => {
              setForm(initial);
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
        aria-label="Cost result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        {result && input ? (
          <>
            <h2 className="text-title-2 text-label">Your estimated costs</h2>
            <p className="text-callout text-label-secondary mt-2">
              Treated as a {result.small ? "small or charitable" : "medium or large"} sponsor.
            </p>
            <p className="text-callout text-label-secondary mt-2">
              CoS employment: {input.months} months. Estimated visa period: {result.visaPeriod}.
            </p>
            <p className="text-footnote text-label-secondary mt-2">
              Assumes permission starts on the employment start date, with the same dates for
              dependants and children under 18 at application. Earlier visa grants or different
              dependant dates need review using actual visa dates and may change IHS. Health and
              Care applicants and their dependants pay no IHS.
            </p>
            <h3 className="text-headline text-label mt-4">Employer must pay</h3>
            <dl className="text-callout text-label mt-2 space-y-1">
              <Row label="Licence fee" value={result.licenceFee} />
              {result.licencePriorityFee ? (
                <Row label="Faster licence decision" value={result.licencePriorityFee} />
              ) : null}
              <Row
                label={`Certificate of sponsorship × ${input.workers}`}
                value={result.cosFee * input.workers}
              />
              <Row
                label={`Immigration Skills Charge × ${input.workers}${result.skillsChargeExempt ? " (exempt)" : ""}`}
                value={result.skillsCharge * input.workers}
              />
              <Row label="Employer total" value={result.employerTotal} strong />
            </dl>
            <h3 className="text-headline text-label mt-4">Worker-side costs</h3>
            <dl className="text-callout text-label mt-2 space-y-1">
              <Row label="Visa fee per person" value={result.visaFeePerPerson} />
              {result.speedFeePerPerson ? (
                <Row label="Faster decision per person" value={result.speedFeePerPerson} />
              ) : null}
              <Row label="Healthcare surcharge, adult" value={result.healthSurchargeAdult} />
              <Row label="Healthcare surcharge, child" value={result.healthSurchargeChild} />
              <Row label="Worker-side total" value={result.workerSideTotal} strong />
            </dl>
            <p className="text-headline text-label mt-4">Grand total: {gbp(result.grandTotal)}</p>
            <p className="text-footnote text-label-secondary mt-3">
              The licence fee, certificate fee and skills charge must be paid by the sponsor; asking
              the worker to pay them can put the licence at risk. Employers may choose to cover visa
              fees and the healthcare surcharge.
            </p>
            <h3 className="text-headline text-label mt-5">Compare certificate lengths</h3>
            <table className="text-footnote text-label mt-2 w-full text-left">
              <caption className="text-label-secondary text-left">
                Total cost by certificate length, using the same visa start and dependant
                assumptions. IHS includes{" "}
                {input.gpTraining ? "4 months for GP specialty training" : "14 days after CoS end"}.
              </caption>
              <thead className="text-label-secondary">
                <tr>
                  <th scope="col">Months</th>
                  <th scope="col">Estimated visa period</th>
                  <th scope="col">Employer</th>
                  <th scope="col">Worker side</th>
                  <th scope="col">Total</th>
                </tr>
              </thead>
              <tbody>
                {compareCertificateLengths(input).map(({ months, result: row }) => (
                  <tr key={months}>
                    <th scope="row" className="font-normal">
                      {months}
                    </th>
                    <td>{row.visaPeriod}</td>
                    <td>{gbp(row.employerTotal)}</td>
                    <td>{gbp(row.workerSideTotal)}</td>
                    <td>{gbp(row.grandTotal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            {error
              ? "Incomplete: fix the highlighted answer to see the costs."
              : "Answer the questions or choose an example; the costs update as you go."}
          </p>
        )}
      </section>
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 ${strong ? "font-semibold" : ""}`}>
      <dt>{label}</dt>
      <dd>{gbp(value)}</dd>
    </div>
  );
}
