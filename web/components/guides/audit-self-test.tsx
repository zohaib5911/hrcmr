"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  auditQuestions,
  scoreAudit,
  type AuditAnswer,
  type AuditAnswers,
} from "@/lib/guides/audit";

const options: readonly [AuditAnswer, string][] = [
  ["yes", "Yes"],
  ["no", "No"],
  ["unsure", "Not sure"],
];

export function AuditSelfTest() {
  const [answers, setAnswers] = useState<AuditAnswers>({});
  const [showResult, setShowResult] = useState(false);
  const score = scoreAudit(answers);
  const complete = score.answered === score.total;

  return (
    <section aria-labelledby="audit-title" className="border-separator mt-10 border-t pt-8">
      <h2 id="audit-title" className="text-title-2 text-label">
        26-question audit self-test
      </h2>
      <p className="text-body text-label-secondary mt-3">
        Answer every question. Yes means you can show evidence. Answers stay in this page’s memory
        and disappear when you reset or reload. No answers are sent or saved.
      </p>
      <form
        className="mt-6 space-y-6"
        onSubmit={(event) => {
          event.preventDefault();
          if (complete) setShowResult(true);
        }}
      >
        {auditQuestions.map(([category, question], index) => (
          <fieldset key={question} className="border-separator rounded-card border p-4">
            <legend className="text-headline text-label px-1">
              {index + 1}. {question}
            </legend>
            <p className="text-caption text-label-secondary">{category}</p>
            <div className="mt-3 flex flex-wrap gap-4">
              {options.map(([value, label]) => (
                <label
                  key={value}
                  className="text-body text-label hit-target inline-flex cursor-pointer items-center gap-2"
                >
                  <input
                    type="radio"
                    name={`audit-${index}`}
                    value={value}
                    required
                    checked={answers[index] === value}
                    onChange={() => {
                      setAnswers((current) => ({ ...current, [index]: value }));
                      setShowResult(false);
                    }}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <p role="status" className="text-body text-label-secondary">
          {score.answered} of {score.total} answered
        </p>
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={!complete}>
            Show my score
          </Button>
          <Button
            variant="gray"
            onClick={() => {
              setAnswers({});
              setShowResult(false);
            }}
          >
            Reset answers
          </Button>
        </div>
        {showResult && complete ? (
          <div role="status" className="bg-fill-secondary rounded-card space-y-3 p-5">
            <h3 className="text-title-3 text-label">
              Preparation score: {score.yes} / {score.total} ({score.percent}%)
            </h3>
            <p className="text-body text-label-secondary">
              This counts Yes answers, not legal compliance. There is no pass mark. It cannot
              predict a Home Office decision. Review every No or Not sure answer, regardless of your
              score.
            </p>
            {score.yes === score.total ? (
              <p>Keep testing these controls and checking current guidance.</p>
            ) : (
              <ul className="list-disc space-y-3 pl-5">
                {auditQuestions.map(([, question, action], index) =>
                  answers[index] !== "yes" ? (
                    <li key={question}>
                      <strong>{question}</strong> {action}
                    </li>
                  ) : null,
                )}
              </ul>
            )}
          </div>
        ) : null}
      </form>
    </section>
  );
}
