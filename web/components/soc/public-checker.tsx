"use client";

import { type FormEvent, useEffect, useState } from "react";

import { Turnstile, TURNSTILE_SITE_KEY } from "@/components/auth/turnstile";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { NumberField } from "@/components/ui/number-field";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { todayIso } from "@/lib/ui/dates";

import { DISCLAIMER, verdictText } from "./results";

type Hit = components["schemas"]["PublicHitOut"];
type Result = components["schemas"]["PublicCheckOut"];
type Nation = components["schemas"]["PublicCheckIn"]["work_nation"];
type SalaryPer = components["schemas"]["PublicCheckIn"]["salary_per"];

const NATIONS: readonly Nation[] = ["England", "Scotland", "Wales", "Northern Ireland"];
const PER: readonly [SalaryPer, string][] = [
  ["year", "a year"],
  ["month", "a month"],
  ["week", "a week"],
  ["hour", "an hour"],
];
// Without a Turnstile site key (development), the server accepts this placeholder, as the apply form does.
const NO_TURNSTILE = "no-turnstile";

/** The free checker: search a job title, pick a code, and see the salary table. No CV, no AI. */
export function PublicSalaryChecker() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [code, setCode] = useState<Hit | null>(null);
  const [hours, setHours] = useState<number | null>(37.5);
  const [salary, setSalary] = useState<number | null>(null);
  const [per, setPer] = useState<SalaryPer>("year");
  const [nation, setNation] = useState<Nation>("England");
  const [cosDate, setCosDate] = useState(todayIso());
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) return;
    let active = true;
    const timer = setTimeout(() => {
      void attempt((c) => c.GET("/public/soc/search", { params: { query: { q: term } } })).then(
        (outcome) => {
          if (!active) return;
          if (outcome.ok) setHits(outcome.data.results);
          else setProblem(outcome.problem);
        },
      );
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  async function check(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!code) return setFormError("Choose the occupation code first.");
    if (salary === null || hours === null || hours <= 0) {
      return setFormError("Enter the hours and the offered salary.");
    }
    if (TURNSTILE_SITE_KEY && !token) return setFormError("Please complete the check.");
    setBusy(true);
    setProblem(null);
    setResult(null);
    const outcome = await attempt((c) =>
      c.POST("/public/soc/salary-check", {
        body: {
          soc_code: code.code,
          weekly_hours: hours,
          offered_salary: salary,
          salary_per: per,
          work_nation: nation,
          cos_assignment_date: cosDate || null,
          turnstile_token: token ?? NO_TURNSTILE,
        },
      }),
    );
    setBusy(false);
    if (!outcome.ok) return setProblem(outcome.problem);
    setResult(outcome.data);
  }

  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <section aria-labelledby="find-heading" className="grid content-start gap-4">
        <h2 id="find-heading" className="text-headline text-label">
          1. Find the occupation code
        </h2>
        <TextField
          label="Job title"
          name="job_title"
          autoComplete="off"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setCode(null);
            setResult(null);
          }}
          hint="For example: Adviser, sales, or Bricklayer"
        />
        {hits.length > 0 && !code ? (
          <ul className="grid gap-2" aria-label="Matching codes">
            {hits.map((hit) => (
              <li key={hit.code}>
                <Button
                  variant="gray"
                  className="w-full justify-start text-left"
                  onClick={() => setCode(hit)}
                >
                  {hit.code} {hit.title}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {code ? (
          <p className="text-callout">
            Code <strong>{code.code}</strong>: {code.title}{" "}
            <button
              type="button"
              className="text-tint underline"
              onClick={() => {
                setCode(null);
                setResult(null);
              }}
            >
              Choose another
            </button>
          </p>
        ) : null}
      </section>

      <section aria-labelledby="pay-heading" className="grid content-start gap-4">
        <h2 id="pay-heading" className="text-headline text-label">
          2. Check the salary
        </h2>
        <form onSubmit={check} noValidate className="grid gap-4" aria-label="Salary">
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              label="Hours a week"
              unit="hours"
              value={hours}
              onChange={setHours}
              min={0}
              max={168}
            />
            <NumberField
              label="Offered salary"
              unit="currency"
              value={salary}
              onChange={setSalary}
              min={0}
            />
            <Select
              label="Salary is paid"
              value={per}
              onChange={(event) => setPer(event.target.value as SalaryPer)}
            >
              {PER.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
            <Select
              label="Work location"
              value={nation}
              onChange={(event) => setNation(event.target.value as Nation)}
            >
              {NATIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
            <TextField
              label="Certificate of Sponsorship date"
              type="date"
              value={cosDate}
              onChange={(event) => setCosDate(event.target.value)}
            />
          </div>
          {TURNSTILE_SITE_KEY ? <Turnstile onToken={setToken} /> : null}
          {formError ? <Alert tone="warning" title={formError} /> : null}
          <div>
            <Button type="submit" disabled={busy || !code}>
              {busy ? "Checking…" : "Show the salary table"}
            </Button>
          </div>
        </form>
      </section>

      {problem ? (
        <div className="lg:col-span-2">
          <Alert tone="danger" title="That did not work">
            {problem.message}
          </Alert>
        </div>
      ) : null}

      {result ? (
        <section aria-label="Salary table" className="grid gap-4 lg:col-span-2">
          <Card>
            <CardHeader
              title={`${result.soc_code} ${result.title}`}
              description={`Rules: ${result.rules_version_name}, effective ${result.rules_effective_from}`}
              headingLevel={3}
              actions={<StatusChip tone="neutral">{result.eligibility}</StatusChip>}
            />
            <CardBody className="grid gap-4 pb-5">
              <div className="overflow-x-auto">
                <table className="text-callout w-full min-w-[30rem] border-collapse text-left">
                  <thead>
                    <tr className="text-footnote text-label-secondary">
                      <th className="py-2 pr-3 font-medium">Option</th>
                      <th className="py-2 pr-3 font-medium">Criteria</th>
                      <th className="py-2 pr-3 font-medium">Minimum required</th>
                      <th className="py-2 font-medium">Meets</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.options.map((option) => (
                      <tr key={option.option} className="border-separator border-t">
                        <td className="py-2 pr-3">{option.option}</td>
                        <td className="py-2 pr-3">{option.criteria_key.replace(/_/g, " ")}</td>
                        <td className="py-2 pr-3">
                          {option.minimum_required === null
                            ? "Not applicable"
                            : `£${option.minimum_required}`}
                        </td>
                        <td className="py-2">
                          {option.meets === null
                            ? "Needs a band or role"
                            : option.meets
                              ? "Yes"
                              : "No"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-callout">{verdictText(result.verdict)}</p>
              {result.notes.length > 0 ? (
                <ul className="text-footnote text-label-secondary list-disc pl-5">
                  {result.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
              <p className="text-footnote text-label-secondary">{DISCLAIMER}</p>
            </CardBody>
          </Card>
        </section>
      ) : null}
    </div>
  );
}
