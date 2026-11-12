"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { TextField } from "@/components/ui/text-field";
import {
  checkSettlement,
  settlementRoutes,
  type SettlementInput,
  type SettlementResult,
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

export function IlrCitizenshipChecker() {
  const [input, setInput] = useState(initial);
  const [result, setResult] = useState<SettlementResult | null>(null);
  const [error, setError] = useState("");
  function update<K extends keyof SettlementInput>(key: K, value: SettlementInput[K]) {
    setInput((previous) => ({ ...previous, [key]: value }));
    setResult(null);
    setError("");
  }
  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            setResult(checkSettlement(input));
            setError("");
          } catch (error) {
            setResult(null);
            setError(error instanceof Error ? error.message : "Check your answers.");
          }
        }}
      >
        <h2 className="text-title-2 text-label">Your residence</h2>
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
        <TextField
          label="Qualifying route residence start"
          type="date"
          required
          value={input.startDate}
          onChange={(event) => update("startDate", event.target.value)}
          hint="First qualifying day in the UK, not automatically the visa issue date. Confirm which previous visas count."
        />
        <TextField
          label="UK residence start for citizenship"
          type="date"
          required
          value={input.residenceStart}
          onChange={(event) => update("residenceStart", event.target.value)}
          hint="May predate your current visa pathway. Excluded periods and gaps need review."
        />
        <TextField
          label="Actual ILR grant date (optional)"
          type="date"
          value={input.settledDate}
          onChange={(event) => update("settledDate", event.target.value)}
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
          <legend className="text-title-3 text-label mb-3">Absences in whole days</legend>
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
          <Button type="submit">Check timeline</Button>
          <Button
            type="button"
            variant="gray"
            onClick={() => {
              setInput(initial);
              setResult(null);
              setError("");
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
              Qualifying residence begins: <time dateTime={input.startDate}>{input.startDate}</time>
            </li>
            <li>
              ILR qualifying-residence milestone:{" "}
              <time dateTime={result.qualifyingDate}>{result.qualifyingDate}</time>.{" "}
              {result.settlementReview
                ? "Individual residence review required."
                : "Subject to all settlement conditions."}
            </li>
            <li>
              {result.indicative
                ? "Indicative citizenship milestone"
                : "Earliest citizenship residence milestone"}
              : <time dateTime={result.citizenshipDate}>{result.citizenshipDate}</time>.{" "}
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
        <p className="text-callout text-label-secondary">
          Enter your residence and travel details to see conditional settlement and citizenship
          milestones.
        </p>
      )}
    </div>
  );
}
