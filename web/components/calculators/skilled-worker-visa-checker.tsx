"use client";

import { useEffect, useMemo, useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { NumberField } from "@/components/ui/number-field";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import type { components } from "@/lib/api/client";
import { attempt } from "@/lib/auth/request";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import {
  checkSkilledWorkerVisa,
  findOccupation,
  FULL_TIME_HOURS,
  visaCheckerSources,
  type Situation,
  type VisaInput,
} from "@/lib/calculators/skilled-worker-visa-checker";

type Hit = components["schemas"]["PublicHitOut"];

const initial: VisaInput = {
  code: "",
  salary: 0,
  weeklyHours: FULL_TIME_HOURS,
  situation: "new",
  phdRelevant: false,
  phdStem: false,
  newEntrant: false,
  dependantPartner: false,
  dependantChildren: 0,
  previousSkilledWorkerBeforeJan2026: false,
};
/**
 * Example scenarios. They fill in the form from the local occupation table, so choosing one
 * sends nothing; they are illustrations, not a prediction for any application.
 */
export const visaPresets: readonly CalculatorPreset<Partial<VisaInput> & { code: string }>[] = [
  {
    id: "developer",
    label: "Software developer on £60,000",
    values: { code: "2134", salary: 60000 },
  },
  {
    id: "new-entrant",
    label: "Software developer, new entrant on £40,000",
    values: { code: "2134", salary: 40000, newEntrant: true },
  },
  {
    id: "engineer-family",
    label: "Mechanical engineer on £40,000 with a partner and child",
    values: { code: "2122", salary: 40000, dependantPartner: true, dependantChildren: 1 },
  },
];

const gbp = (n: number) => `£${n.toLocaleString("en-GB")}`;

function YesNo({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <Select
      label={label}
      {...(hint ? { hint } : {})}
      value={value ? "yes" : "no"}
      onChange={(event) => onChange(event.target.value === "yes")}
    >
      <option value="no">No</option>
      <option value="yes">Yes</option>
    </Select>
  );
}

export function SkilledWorkerVisaChecker() {
  const [input, setInput] = useState<VisaInput>(initial);
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<Hit | null>(null);
  const [hits, setHits] = useState<Hit[]>([]);
  const [lookupMessage, setLookupMessage] = useState("");
  const [touched, setTouched] = useState(false);
  // Live result: recalculated locally on every change once the job and salary are entered.
  const ready = input.code !== "" && input.salary > 0;
  const result = useMemo(
    () => (ready ? checkSkilledWorkerVisa(input, chosen ?? undefined) : null),
    [ready, input, chosen],
  );
  const incomplete = !touched
    ? null
    : !input.code
      ? "Incomplete: search for the job and choose an occupation from the list."
      : !(input.salary > 0)
        ? "Incomplete: enter the annual salary offered."
        : null;
  useEffect(() => {
    const term = query.trim();
    if (chosen || term.length < 2) return;
    let active = true;
    const timer = setTimeout(async () => {
      // Only the occupation query goes to the lookup. All applicant answers stay local.
      if (/^[1-9]\d{3}$/.test(term)) {
        const outcome = await attempt((c) =>
          c.GET("/public/soc/{code}", { params: { path: { code: term } } }),
        );
        if (!active) return;
        setHits(outcome.ok ? [outcome.data] : []);
        setLookupMessage(outcome.ok ? "" : outcome.problem.message);
      } else {
        const outcome = await attempt((c) =>
          c.GET("/public/soc/search", { params: { query: { q: term } } }),
        );
        if (!active) return;
        setHits(outcome.ok ? outcome.data.results : []);
        setLookupMessage(
          outcome.ok
            ? outcome.data.results.length
              ? ""
              : "No matching occupations. Try another title or SOC code."
            : outcome.problem.message,
        );
      }
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, chosen]);

  function update<K extends keyof VisaInput>(key: K, value: VisaInput[K]) {
    setInput((previous) => ({ ...previous, [key]: value }));
    setTouched(true);
  }

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
        <PresetChips
          presets={visaPresets}
          onSelect={(preset) => {
            const occupation = findOccupation(preset.values.code);
            const hit = occupation ? { code: occupation.code, title: occupation.title } : null;
            setInput({ ...initial, ...preset.values });
            setChosen(hit);
            setHits([]);
            setLookupMessage("");
            setQuery(hit ? `${hit.code} ${hit.title}` : "");
            setTouched(true);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> The job
        </h2>
        <TextField
          label="SOC code or job title"
          autoComplete="off"
          hint="Search the public SOC 2020 list, for example 2134 or software developer. Only this search is sent; salary and personal answers stay in this page."
          maxLength={100}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setChosen(null);
            setHits([]);
            setLookupMessage("");
            update("code", "");
          }}
        />
        {lookupMessage ? (
          <p role="status" className="text-callout text-label-secondary">
            {lookupMessage}
          </p>
        ) : null}
        {!chosen && hits.length > 0 ? (
          <ul className="grid gap-2" aria-label="Matching occupations">
            {hits.map((hit) => (
              <li key={hit.code}>
                <Button
                  variant="gray"
                  onClick={() => {
                    setChosen(hit);
                    setHits([]);
                    setLookupMessage("");
                    setQuery(`${hit.code} ${hit.title}`);
                    update("code", hit.code);
                  }}
                >
                  {hit.code} {hit.title}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        <NumberField
          label="Annual salary offered"
          unit="currency"
          min={0}
          value={input.salary || null}
          onChange={(value) => update("salary", value ?? 0)}
          hint="Guaranteed basic gross pay only: no bonus, overtime or allowances."
        />
        <NumberField
          label="Weekly hours"
          unit="hours"
          min={0}
          max={168}
          value={input.weeklyHours}
          onChange={(value) => update("weeklyHours", value ?? 0)}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">2.</span> The applicant
        </h2>
        <Select
          label="Applicant situation"
          value={input.situation}
          onChange={(event) => update("situation", event.target.value as Situation)}
        >
          <option value="new">
            New applicant, or no continuous permission since before 22 July 2025
          </option>
          <option value="continuing">
            Granted Skilled Worker permission before 22 July 2025, continuous since
          </option>
        </Select>
        <YesNo
          label="Relevant PhD?"
          value={input.phdRelevant}
          onChange={(value) => update("phdRelevant", value)}
        />
        <YesNo
          label="PhD in a STEM subject relevant to the job?"
          value={input.phdStem}
          onChange={(value) => update("phdStem", value)}
        />
        <YesNo
          label="New entrant at the start of their career?"
          value={input.newEntrant}
          onChange={(value) => update("newEntrant", value)}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">3.</span> Dependants and English
        </h2>
        <YesNo
          label="Is a partner applying as a dependant?"
          value={input.dependantPartner}
          onChange={(value) => update("dependantPartner", value)}
        />
        <NumberField
          label="Dependent children applying"
          min={0}
          decimals={0}
          value={input.dependantChildren}
          onChange={(value) => update("dependantChildren", value ?? 0)}
        />
        <YesNo
          label="Extending a Skilled Worker visa held before 8 January 2026?"
          value={input.previousSkilledWorkerBeforeJan2026}
          onChange={(value) => update("previousSkilledWorkerBeforeJan2026", value)}
        />
        <div className="flex flex-wrap gap-3">
          <Button
            variant="gray"
            onClick={() => {
              setInput(initial);
              setQuery("");
              setChosen(null);
              setHits([]);
              setLookupMessage("");
              setTouched(false);
            }}
          >
            Reset answers
          </Button>
        </div>
      </form>
      <section
        aria-label="Checker result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">
              {result.status === "needs-review"
                ? "Needs review"
                : result.status === "invalid-code"
                  ? "Choose a valid occupation"
                  : result.eligible
                    ? "Salary requirement met"
                    : "Not eligible on these answers"}
            </h2>
            {result.status === "needs-review" ? (
              <p className="text-callout text-label-secondary mt-2">
                {chosen?.code} {chosen?.title}
              </p>
            ) : null}
            {result.occupation ? (
              <p className="text-callout text-label-secondary mt-2">
                {result.occupation.code} {result.occupation.title}. Going rate{" "}
                {gbp(result.occupation.goingRate)} for {FULL_TIME_HOURS} hours a week.
              </p>
            ) : null}
            <div className="text-callout text-label-secondary mt-3 space-y-3">
              {result.messages.map((text) => (
                <p key={text}>{text}</p>
              ))}
            </div>
            {result.status === "needs-review" ? (
              <p className="text-callout mt-3">
                <a href={visaCheckerSources[1]?.url} className="text-accent-text underline">
                  Review the official Skilled Occupations appendix
                </a>
              </p>
            ) : null}
            {result.eligibleOccupation ? (
              <table className="text-footnote text-label mt-4 w-full text-left">
                <caption className="sr-only">Minimum salary for each points option</caption>
                <thead className="text-label-secondary">
                  <tr>
                    <th scope="col" className="py-2 pr-2">
                      Option
                    </th>
                    <th scope="col" className="py-2 pr-2">
                      Minimum salary
                    </th>
                    <th scope="col" className="py-2">
                      Result
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.options.map((o) => (
                    <tr key={o.option}>
                      <th scope="row" className="py-2 pr-2 font-normal">
                        {o.label}
                      </th>
                      <td className="py-2 pr-2">
                        {o.requiredSalary === null ? "n/a" : gbp(o.requiredSalary)}
                      </td>
                      <td className="py-2">
                        {o.requiredSalary === null ? o.reason : o.met ? "Met" : "Not met"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            <h3 className="text-headline text-label mt-5">Dependants</h3>
            <p className="text-callout text-label-secondary mt-2">
              {result.dependantFunds > 0
                ? `Maintenance funds of at least ${gbp(result.dependantFunds)} are needed for dependants, in addition to any funds you need yourself, unless an exemption applies.`
                : "No dependants entered. Partner and child applications each need their own funds and evidence."}
            </p>
            <h3 className="text-headline text-label mt-5">English language</h3>
            <p className="text-callout text-label-secondary mt-2">{result.english}</p>
            <p className="text-footnote text-label-secondary mt-5">
              This is a salary and occupation guide, not a decision on any visa application.
            </p>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            {incomplete ??
              "Choose the job and enter the salary, or pick an example; the result updates as you go."}
          </p>
        )}
      </section>
    </div>
  );
}
