"use client";

import { ScanSearch } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan, useMe } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { attempt, type Problem } from "@/lib/auth/request";

import { CheckForm, type MatchBody } from "./check-form";
import { CheckHistory, type Summary } from "./history";
import { CvMatchPanel } from "./cv-match";
import {
  type Candidate,
  type Check,
  DISCLAIMER,
  MatchResults,
  type Match,
  SavedCheck,
} from "./results";

type Busy = "match" | "save" | "confirm" | "pdf" | "open" | null;

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

type Props = {
  /** Inside a sheet from another form: no page heading, no history, one column. */
  embedded?: boolean;
  /** Called with the code once it is confirmed (the "Find code" embeds fill their field with it). */
  onConfirmed?: (code: string) => void;
};

/** The sponsorship job checker: the job, the ranked codes, a saved check, its confirmation and PDF. */
export function SponsorshipChecker({ embedded = false, onConfirmed }: Props = {}) {
  const can = useCan();
  const aiAvailable = useMe()?.ai_available ?? false;
  const mayRead = can("soc.check.read");
  const mayRun = can("soc.check.run");
  const [body, setBody] = useState<MatchBody | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [saved, setSaved] = useState<Check | null>(null);
  const [history, setHistory] = useState<Summary[] | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  const loadHistory = useCallback(async () => {
    const result = await attempt((c) => c.GET("/soc/checks"));
    if (result.ok) setHistory(result.data.items);
    else setProblem(result.problem);
  }, []);

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void attempt((c) => c.GET("/soc/checks")).then((result) => {
      if (!active) return;
      if (result.ok) setHistory(result.data.items);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead]);

  async function runMatch(next: MatchBody) {
    setBody(next);
    setBusy("match");
    setProblem(null);
    const result = await attempt((c) => c.POST("/soc/match", { body: next }));
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    setMatch(result.data);
    setSaved(null);
  }

  async function chooseCode(candidate: Candidate) {
    if (!body) return;
    setBusy("save");
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/soc/checks", {
        body: {
          job_title: body.job_title,
          job_description: body.job_description,
          soc_code: candidate.code,
          check: body.check,
        },
      }),
    );
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    setSaved(result.data);
    void loadHistory();
  }

  async function confirm() {
    if (!saved) return;
    setBusy("confirm");
    setProblem(null);
    const result = await attempt((c) =>
      c.POST("/soc/checks/{check_id}/confirm", { params: { path: { check_id: saved.id } } }),
    );
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    setSaved(result.data);
    void loadHistory();
    onConfirmed?.(result.data.soc_code);
  }

  function startAgain() {
    setMatch(null);
    setSaved(null);
    setProblem(null);
  }

  async function openCheck(id: string) {
    setBusy("open");
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/soc/checks/{check_id}", { params: { path: { check_id: id } } }),
    );
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    setMatch(null);
    setSaved(result.data);
  }

  async function downloadReport() {
    if (!saved) return;
    setBusy("pdf");
    setProblem(null);
    const result = await attempt((c) =>
      c.GET("/soc/checks/{check_id}/report.pdf", {
        params: { path: { check_id: saved.id } },
        parseAs: "blob",
      }),
    );
    setBusy(null);
    if (!result.ok) return setProblem(result.problem);
    download(result.data, `soc-check-${saved.soc_code}.pdf`);
  }

  if (!mayRead) {
    return (
      <EmptyState
        icon={ScanSearch}
        title="The sponsorship checker is not open to you"
        description="Ask a company administrator or recruiter to run the check for you."
      />
    );
  }

  return (
    <>
      {embedded ? null : (
        <PageHeader
          title="Sponsorship checker"
          description="Check whether a job can be sponsored, find its occupation code and test the salary."
        />
      )}
      {problem ? (
        <Alert tone="danger" title="That did not work" className="mb-6">
          {problem.message}
        </Alert>
      ) : null}
      <div
        className={
          embedded ? "grid gap-8" : "grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]"
        }
      >
        <section aria-labelledby="job-heading" className="grid content-start gap-4">
          <h2 id="job-heading" className="text-headline text-label">
            The job
          </h2>
          <CheckForm busy={busy === "match"} canRun={mayRun} onSubmit={runMatch} />
        </section>
        <section aria-live="polite" className="grid content-start gap-6">
          {busy === "match" ? (
            <p className="text-callout text-label-secondary">Checking the job…</p>
          ) : null}
          {match || saved ? (
            <div>
              <Button variant="gray" onClick={startAgain}>
                Start a new check
              </Button>
            </div>
          ) : null}
          {match && !saved ? (
            <MatchResults
              match={match}
              busy={busy !== null}
              canRun={mayRun}
              onChoose={chooseCode}
            />
          ) : null}
          {saved ? (
            <SavedCheck
              check={saved}
              busy={busy !== null}
              canRun={mayRun}
              onConfirm={confirm}
              onDownload={downloadReport}
            />
          ) : null}
          {saved && aiAvailable ? (
            <CvMatchPanel
              socCode={saved.soc_code}
              jobDescription={saved.job_description}
              canRun={mayRun}
            />
          ) : null}
          {!match && !saved && busy !== "match" ? (
            <EmptyState
              icon={ScanSearch}
              title="No check yet"
              description="Enter the job on the left. You will see the best occupation code, whether the job qualifies and the minimum pay."
            />
          ) : null}
          {embedded ? null : (
            <CheckHistory items={history} disabled={busy !== null} onOpen={openCheck} />
          )}
        </section>
      </div>
      <p className="text-footnote text-label-secondary mt-10">
        {DISCLAIMER} Check the rules on GOV.UK, or with an adviser or CASCOT, before you rely on a
        result.
      </p>
    </>
  );
}
