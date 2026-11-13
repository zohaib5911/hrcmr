"use client";

import { DatePicker } from "@/components/ui/date-picker";

import { useMemo, useState } from "react";

import { PresetChips } from "@/components/calculators/preset-chips";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { CalculatorPreset } from "@/lib/calculators/frame";
import {
  checkRightToWork,
  type Answer,
  type Duty,
  type Engagement,
  type RightToWorkInput,
} from "@/lib/calculators/right-to-work-october-2026-checker";

const initial: RightToWorkInput = {
  engagement: "employee",
  workInUK: "unsure",
  independentBusiness: "unsure",
  employmentStart: "",
  contractChain: "unsure",
  substitution: "unsure",
  arrangementStart: "",
};
/** Example arrangements: they only fill in the form; the result comes from the same rules. */
export const rightToWorkPresets: readonly CalculatorPreset<Partial<RightToWorkInput>>[] = [
  {
    id: "employee",
    label: "UK employee starting November 2026",
    values: {
      engagement: "employee",
      workInUK: "yes",
      independentBusiness: "no",
      employmentStart: "2026-11-02",
      contractChain: "no",
      substitution: "no",
    },
  },
  {
    id: "matching",
    label: "Online matching service",
    values: {
      engagement: "matching",
      workInUK: "yes",
      independentBusiness: "no",
      employmentStart: "2026-11-02",
      contractChain: "no",
      substitution: "no",
      arrangementStart: "2026-11-02",
    },
  },
  {
    id: "independent",
    label: "Independent sub-contractor business",
    values: {
      engagement: "subcontractor",
      workInUK: "yes",
      independentBusiness: "yes",
      contractChain: "no",
      substitution: "no",
    },
  },
  { id: "overseas", label: "Work done outside the UK", values: { workInUK: "no" } },
];

const labels: Record<Duty, string> = {
  applies: "In scope",
  outside: "Outside this scope",
  review: "Needs review",
  predates: "Predates commencement — review other duties",
};

function AnswerSelect({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: Answer;
  onChange: (value: Answer) => void;
}) {
  return (
    <Select
      label={label}
      {...(hint ? { hint } : {})}
      value={value}
      onChange={(event) => onChange(event.target.value as Answer)}
    >
      <option value="unsure">Not sure</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </Select>
  );
}

export function RightToWorkChecker() {
  const [input, setInput] = useState<RightToWorkInput>(initial);
  const [touched, setTouched] = useState(false);
  // Live result: recalculated locally on every change once the user has answered something.
  const result = useMemo(() => (touched ? checkRightToWork(input) : null), [input, touched]);
  function update<K extends keyof RightToWorkInput>(key: K, value: RightToWorkInput[K]) {
    setInput((previous) => ({ ...previous, [key]: value }));
    setTouched(true);
  }
  const hasExtended =
    input.engagement === "matching" ||
    input.contractChain === "yes" ||
    input.substitution === "yes";
  const needsReview = result ? result.direct === "review" || result.extended === "review" : false;

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
        <PresetChips
          presets={rightToWorkPresets}
          onSelect={(preset) => {
            setInput({ ...initial, ...preset.values });
            setTouched(true);
          }}
        />
        <h2 className="text-title-2 text-label">
          <span className="text-accent-text">1.</span> The working arrangement
        </h2>
        <Select
          label="Engagement type"
          value={input.engagement}
          onChange={(event) => update("engagement", event.target.value as Engagement)}
        >
          <option value="employee">Employee</option>
          <option value="worker">Worker contract</option>
          <option value="subcontractor">Individual sub-contractor</option>
          <option value="matching">Online matching service</option>
          <option value="other">Other</option>
        </Select>
        <AnswerSelect
          label="Is the work carried out in the UK?"
          value={input.workInUK}
          onChange={(value) => update("workInUK", value)}
        />
        {input.workInUK !== "no" ? (
          <>
            <h2 className="text-title-2 text-label">
              <span className="text-accent-text">2.</span> Who does the work and when
            </h2>
            <AnswerSelect
              label="Buying directly from an independent business?"
              hint="Consider the actual arrangement, not just a self-employed label. For a platform, consider whether the provider operates independently."
              value={input.independentBusiness}
              onChange={(value) => update("independentBusiness", value)}
            />
            <DatePicker
              label="Employment / engagement start date"
              hint="The worker’s start date, not today’s date."
              value={input.employmentStart || null}
              onChange={(value) => update("employmentStart", value ?? "")}
            />
            <h2 className="text-title-2 text-label">
              <span className="text-accent-text">3.</span> Contracts and substitution
            </h2>
            <AnswerSelect
              label="Contracting workers to deliver services onwards?"
              hint="Are you responsible for delivering work to a third party and contracting another employer to fulfil it? Buying a service only for your own use is different."
              value={input.contractChain}
              onChange={(value) => update("contractChain", value)}
            />
            <AnswerSelect
              label="Does the contract permit substitution?"
              value={input.substitution}
              onChange={(value) => update("substitution", value)}
            />
            {hasExtended ? (
              <DatePicker
                label="Relevant contractual arrangement date"
                hint="When the contract chain, matching or substitution arrangement was entered into. Assess renewed or changed arrangements separately."
                value={input.arrangementStart || null}
                onChange={(value) => update("arrangementStart", value ?? "")}
              />
            ) : null}
          </>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button
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
      <section
        aria-label="Checker result"
        aria-live="polite"
        aria-atomic="true"
        className="bg-elevated rounded-control p-5 sm:p-6"
      >
        {result ? (
          <>
            <h2 className="text-title-2 text-label">Your scope check</h2>
            {needsReview ? (
              <p role="status" className="text-callout text-label mt-2">
                Incomplete or needs review: answer the remaining questions, or check the facts
                against the guidance.
              </p>
            ) : null}
            <dl className="text-callout text-label mt-4 space-y-3">
              <div>
                <dt className="font-semibold">Direct check duty</dt>
                <dd>{labels[result.direct]}</dd>
              </div>
              <div>
                <dt className="font-semibold">Extended liability</dt>
                <dd>{labels[result.extended]}</dd>
              </div>
            </dl>
            <div className="text-callout text-label-secondary mt-4 space-y-3">
              {result.explanation.map((text) => (
                <p key={text}>{text}</p>
              ))}
            </div>
            {result.actions.length ? (
              <>
                <h3 className="text-headline text-label mt-5">What to do</h3>
                <ul className="text-callout text-label-secondary mt-2 list-disc space-y-3 pl-5">
                  {result.actions.map((text) => (
                    <li key={text}>{text}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {result.records.length ? (
              <>
                <h3 className="text-headline text-label mt-5">Records to keep</h3>
                <ul className="text-callout text-label-secondary mt-2 list-disc space-y-3 pl-5">
                  {result.records.map((text) => (
                    <li key={text}>{text}</li>
                  ))}
                </ul>
              </>
            ) : null}
            <p className="text-footnote text-label-secondary mt-5">
              This result does not confirm anyone’s right to work or establish a statutory excuse.
            </p>
          </>
        ) : (
          <p className="text-callout text-label-secondary">
            Answer the questions or choose an example; the scope check updates as you go.
          </p>
        )}
      </section>
    </div>
  );
}
