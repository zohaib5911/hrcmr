"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import type { Tone } from "@/lib/ui/status";

export type Match = components["schemas"]["SocMatchOut"];
export type Candidate = components["schemas"]["SocCandidateOut"];
export type Check = components["schemas"]["SocCheckOut"];
type Verdict = components["schemas"]["Verdict"];
type CheckResult = components["schemas"]["CheckResult"];

export const DISCLAIMER = "General guidance, not legal or immigration advice.";

const ELIGIBILITY_TONE: Record<string, Tone> = {
  eligible: "success",
  eligible_transitional: "warning",
  isl: "warning",
  tsl: "warning",
  ineligible: "danger",
};

/** The verdict in words, from the engine's answer. Money stays as the engine computed it. */
export function verdictText(verdict: Verdict): string {
  if (verdict.meets === true) return `Meets the minimum for option ${verdict.option ?? ""}.`;
  if (verdict.meets === false) {
    const hours = verdict.hours_needed
      ? ` The same hourly pay would need ${String(verdict.hours_needed)} hours a week.`
      : "";
    return `Short by £${String(verdict.short_by ?? "")} of the minimum.${hours}`;
  }
  return "Cannot be decided yet: this code needs a band or role (see the notes).";
}

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : `${value}%`;
}

function Disclaimer({ result }: { result: CheckResult }) {
  return (
    <div className="border-separator text-footnote text-label-secondary mt-4 rounded-xl border p-3">
      <p>{DISCLAIMER}</p>
      <p>
        Rules: {result.rules_version_name}, effective {result.rules_effective_from}.
      </p>
    </div>
  );
}

type MatchProps = {
  match: Match;
  busy: boolean;
  canRun: boolean;
  onChoose: (candidate: Candidate) => void;
};

/** The ranked codes for the job. Choosing one saves a draft check for it. */
export function MatchResults({ match, busy, canRun, onChoose }: MatchProps) {
  const [best, ...others] = match.candidates;
  if (!best) {
    return (
      <Alert tone="info" title="No occupation code matched this job">
        Try a shorter or more common job title, or add a description.
      </Alert>
    );
  }
  return (
    <div className="grid gap-4">
      {match.notice ? <Alert tone="info" title={match.notice} /> : null}
      {match.low_confidence ? (
        <Alert tone="warning" title="Low confidence">
          Check with an adviser or CASCOT before you rely on this code.
        </Alert>
      ) : null}
      <Card>
        <CardHeader
          title={`${best.code} ${best.title}`}
          description={
            match.ai_ranked && best.confidence !== null
              ? `Best match, ${best.confidence} out of 100`
              : "Best match, in search order"
          }
          headingLevel={2}
        />
        <CardBody className="grid gap-3 pb-5">
          {best.reason ? <p className="text-callout">{best.reason}</p> : null}
          {best.matched_duties.length > 0 ? (
            <ul className="text-callout list-disc pl-5">
              {best.matched_duties.map((duty) => (
                <li key={duty}>{duty}</li>
              ))}
            </ul>
          ) : null}
          <div>
            <Button onClick={() => onChoose(best)} disabled={busy || !canRun}>
              Check this code
            </Button>
          </div>
        </CardBody>
      </Card>
      {others.length > 0 ? (
        <section aria-label="Other codes" className="grid gap-2">
          <h3 className="text-headline text-label">Other codes that could fit</h3>
          <ul className="grid gap-2">
            {others.map((candidate) => (
              <li
                key={candidate.code}
                className="border-separator flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"
              >
                <span className="text-callout">
                  <span className="font-medium">{candidate.code}</span> {candidate.title}
                </span>
                <Button
                  variant="gray"
                  size="sm"
                  onClick={() => onChoose(candidate)}
                  disabled={busy || !canRun}
                >
                  Check this code
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

type SavedProps = {
  check: Check;
  busy: boolean;
  canRun: boolean;
  onConfirm: () => void;
  onDownload: () => void;
};

/** A saved check: the answer on the rules version it was made with, then confirm and report. */
export function SavedCheck({ check, busy, canRun, onConfirm, onDownload }: SavedProps) {
  const { result } = check;
  const confirmed = check.status === "confirmed";
  const tone = ELIGIBILITY_TONE[result.eligibility.status] ?? "neutral";
  return (
    <Card>
      <CardHeader
        title={`${check.soc_code} ${check.soc_title}`}
        description={`For: ${check.job_title}`}
        actions={
          <StatusChip tone={confirmed ? "success" : "neutral"}>
            {confirmed ? "Confirmed" : "Draft"}
          </StatusChip>
        }
        headingLevel={2}
      />
      <CardBody className="grid gap-5 pb-5">
        <div>
          <StatusChip tone={tone}>{result.eligibility.label}</StatusChip>
        </div>
        <section aria-label="Minimum pay" className="overflow-x-auto" tabIndex={0}>
          {result.options.length === 0 ? (
            <p className="text-callout text-label-secondary">
              The published rules give no pay options for this code.
            </p>
          ) : (
            <table className="text-callout w-full min-w-[32rem] border-collapse text-left">
              <thead>
                <tr className="text-footnote text-label-secondary">
                  <th className="py-2 pr-3 font-medium">Option</th>
                  <th className="py-2 pr-3 font-medium">Criteria</th>
                  <th className="py-2 pr-3 font-medium">Going rate</th>
                  <th className="py-2 pr-3 font-medium">Minimum required</th>
                  <th className="py-2 font-medium">Meets</th>
                </tr>
              </thead>
              <tbody>
                {result.options.map((option) => (
                  <tr key={option.option} className="border-separator border-t">
                    <td className="py-2 pr-3">{option.option}</td>
                    <td className="py-2 pr-3">{option.criteria_key.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-3">{percent(option.going_rate_pct)}</td>
                    <td className="py-2 pr-3">
                      {option.minimum_required === null
                        ? "Not applicable"
                        : `£${option.minimum_required}`}
                    </td>
                    <td className="py-2">
                      {option.meets === null ? "Needs a band or role" : option.meets ? "Yes" : "No"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        <p className="text-callout">{verdictText(result.verdict)}</p>
        <p className="text-callout">
          Dependants allowed: {result.dependants_allowed ? "yes" : "no"}.
        </p>
        {result.notes.length > 0 ? (
          <ul className="text-footnote text-label-secondary list-disc pl-5">
            {result.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {confirmed ? (
            <Button onClick={onDownload} disabled={busy}>
              Download the report (PDF)
            </Button>
          ) : (
            <Button onClick={onConfirm} disabled={busy || !canRun}>
              Confirm this code
            </Button>
          )}
        </div>
        <Disclaimer result={result} />
      </CardBody>
    </Card>
  );
}
