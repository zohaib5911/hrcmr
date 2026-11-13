"use client";

import { PublicDate } from "@/components/marketing/public-content";

import { DatePicker } from "@/components/ui/date-picker";

import { useMemo, useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import {
  checkSettlement,
  settlementRoutes,
  type SettlementInput,
} from "@/lib/calculators/ilr-citizenship-checker";

const initial: SettlementInput = {
  route: "skilled_worker",
  startDate: "",
  residenceStart: "",
  settledDate: "",
  britishSpouse: false,
  rollingAbsences: 0,
  citizenshipAbsences: 0,
  lastYearAbsences: 0,
};

/**
 * Example timelines with made-up dates. They only fill in the form; the milestones come from
 * the same rules data and are never an eligibility verdict.
 */
export const settlementPresets: readonly CalculatorPreset<Partial<SettlementInput>>[] = [
  {
    id: "skilled-worker",
    label: "Skilled Worker since June 2021",
    values: { route: "skilled_worker", startDate: "2021-06-20", residenceStart: "2021-06-20" },
  },
  {
    id: "spouse",
    label: "Settled, married to a British citizen",
    values: {
      route: "family_5",
      startDate: "2020-03-01",
      residenceStart: "2020-03-01",
      settledDate: "2025-04-01",
      britishSpouse: true,
    },
  },
  {
    id: "long-absences",
    label: "Long residence with long absences",
    values: {
      route: "long_residence",
      startDate: "2016-09-01",
      residenceStart: "2016-09-01",
      rollingAbsences: 200,
      citizenshipAbsences: 500,
      lastYearAbsences: 60,
    },
  },
];

function evaluate(input: SettlementInput) {
  if (!input.startDate || !input.residenceStart)
    return {
      result: null,
      error: "",
      incomplete: "Incomplete: enter both residence start dates to see the milestones.",
    };
  try {
    return { result: checkSettlement(input), error: "", incomplete: "" };
  } catch (error) {
    return {
      result: null,
      error: error instanceof Error ? error.message : "Check your answers.",
      incomplete: "",
    };
  }
}

export function IlrCitizenshipChecker() {
  const [input, setInput] = useState(initial);
  const [touched, setTouched] = useState(false);
  // Live result: recalculated locally on every change once the user has answered something.
  const { result, error, incomplete } = useMemo(
    () => (touched ? evaluate(input) : { result: null, error: "", incomplete: "" }),
    [input, touched],
  );
  function update<K extends keyof SettlementInput>(key: K, value: SettlementInput[K]) {
    setInput((previous) => ({ ...previous, [key]: value }));
    setTouched(true);
  }
  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
        <PresetChips
          presets={settlementPresets}
          onSelect={(preset) => {
            setInput({ ...initial, ...preset.values });
            setTouched(true);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> Your residence
        </h2>
        <Select
          label="Visa pathway"
          value={input.route}
          onChange={(event) => update("route", event.target.value)}
        >
          {settlementRoutes.map((route) => (
            <option key={route.id} value={route.id}>
              {route.label}
            </option>
          ))}
        </Select>
        <DatePicker
          label="Qualifying route residence start"
          required
          value={input.startDate || null}
          onChange={(value) => update("startDate", value ?? "")}
          hint="First qualifying day in the UK, not automatically the visa issue date. Confirm which previous visas count."
        />
        <DatePicker
          label="UK residence start for citizenship"
          required
          value={input.residenceStart || null}
          onChange={(value) => update("residenceStart", value ?? "")}
          hint="May predate your current visa pathway. Excluded periods and gaps need review."
        />
        <DatePicker
          label="Actual ILR grant date (optional)"
          value={input.settledDate || null}
          onChange={(value) => update("settledDate", value ?? "")}
          hint="Leave blank for an indicative citizenship timeline. An application date is not a grant date."
        />
        <Select
          label="Married to or civil partner of a British citizen?"
          value={input.britishSpouse ? "yes" : "no"}
          onChange={(event) => update("britishSpouse", event.target.value === "yes")}
        >
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </Select>
        <fieldset className="space-y-5">
          <legend className="text-title-2 text-label mb-3">
            <span className="text-accent-text">2.</span> Absences in whole days
          </legend>
          <p className="text-footnote text-label-secondary">
            Use your travel records for the periods ending on your proposed application dates. Count
            whole days abroad; exclude departure and return days. Totals do not resolve historical
            rules or exceptions.
          </p>
          <TextField
            label="Maximum rolling-year absence days"
            hint="Largest number of whole days abroad in any rolling 12 months of qualifying route residence."
            type="number"
            min={0}
            step={1}
            required
            value={Number.isNaN(input.rollingAbsences) ? "" : input.rollingAbsences}
            onChange={(event) =>
              update(
                "rollingAbsences",
                event.target.value === "" ? NaN : Number(event.target.value),
              )
            }
          />
          <TextField
            label={`Days abroad in the citizenship ${input.britishSpouse ? "3" : "5"}-year period`}
            type="number"
            min={0}
            step={1}
            required
            value={Number.isNaN(input.citizenshipAbsences) ? "" : input.citizenshipAbsences}
            onChange={(event) =>
              update(
                "citizenshipAbsences",
                event.target.value === "" ? NaN : Number(event.target.value),
              )
            }
          />
          <TextField
            label="Days abroad in the final 12 months before citizenship"
            type="number"
            min={0}
            step={1}
            required
            value={Number.isNaN(input.lastYearAbsences) ? "" : input.lastYearAbsences}
            onChange={(event) =>
              update(
                "lastYearAbsences",
                event.target.value === "" ? NaN : Number(event.target.value),
              )
            }
          />
        </fieldset>
        {error ? (
          <p role="alert" className="text-danger text-callout">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            variant="gray"
            onClick={() => {
              setInput(initial);
              setTouched(false);
            }}
          >
            Reset answers
          </Button>
        </div>
      </form>
      {result ? (
        <section
          aria-label="Settlement timeline result"
          aria-live="polite"
          className="bg-surface border-separator space-y-4 rounded-xl border p-6"
        >
          <h2 className="text-title-2 text-label">Your conditional timeline</h2>
          <ol className="text-callout text-label space-y-4">
            <li>
              Qualifying residence begins: <PublicDate value={input.startDate} />
            </li>
            <li>
              ILR qualifying-residence milestone: <PublicDate value={result.qualifyingDate} />.{" "}
              {result.settlementReview
                ? "Individual residence review required."
                : "Subject to all settlement conditions."}
            </li>
            <li>
              {result.indicative
                ? "Indicative citizenship milestone"
                : "Earliest citizenship residence milestone"}
              : <PublicDate value={result.citizenshipDate} />.{" "}
              {result.citizenshipReview
                ? "Absences need individual review before applying."
                : "Subject to all citizenship conditions."}
            </li>
          </ol>
          <ul className="text-footnote text-label-secondary list-disc space-y-3 pl-5">
            {result.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      ) : (
        <p aria-live="polite" className="text-callout text-label-secondary">
          {incomplete ||
            "Enter your residence and travel details, or pick an example; the conditional settlement and citizenship milestones update as you go."}
        </p>
      )}
    </div>
  );
}
