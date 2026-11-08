"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

type CvMatch = components["schemas"]["SocCvMatchOut"];

const REMOVED_LABELS: Record<string, string> = {
  link: "web links",
  email: "e-mail addresses",
  phone: "phone numbers",
  postcode: "postcodes",
  address: "street addresses",
};
const MAX_BYTES = 10 * 1024 * 1024;

type Props = {
  socCode: string;
  jobDescription: string;
  canRun: boolean;
};

/** Optional: compares an uploaded CV with the chosen code. Shown only when AI is on for the company. */
export function CvMatchPanel({ socCode, jobDescription, canRun }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CvMatch | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const items: UploadItem[] = file
    ? [{ id: file.name, name: file.name, size: file.size, status: "safe" }]
    : [];

  async function compare() {
    if (!file) return;
    setBusy(true);
    setProblem(null);
    const body = new FormData();
    body.append("cv", file);
    body.append("soc_code", socCode);
    body.append("job_description", jobDescription);
    const outcome = await attempt((c) =>
      c.POST("/soc/resume-match", {
        body: { cv: "", soc_code: socCode, job_description: jobDescription },
        bodySerializer: () => body,
      }),
    );
    setBusy(false);
    if (!outcome.ok) return setProblem(outcome.problem);
    setResult(outcome.data);
  }

  return (
    <Card>
      <CardHeader
        title="Compare a CV (optional)"
        description="Upload a PDF or DOCX. Contact details are taken out before the AI sees it, and the CV is not stored."
        headingLevel={2}
      />
      <CardBody className="grid gap-4 pb-5">
        <FileDrop
          label="CV"
          description="PDF or DOCX, up to 10 MB"
          accept={[".pdf", ".docx"]}
          maxBytes={MAX_BYTES}
          items={items}
          onFiles={(files) => {
            setFile(files[0] ?? null);
            setResult(null);
          }}
          onRemove={() => {
            setFile(null);
            setResult(null);
          }}
          disabled={busy || !canRun}
        />
        <div>
          <Button variant="gray" onClick={compare} disabled={!file || busy || !canRun}>
            Compare the CV
          </Button>
        </div>
        {problem ? (
          <Alert tone="danger" title="The CV could not be compared">
            {problem.message}
          </Alert>
        ) : null}
        {result ? <CvResult result={result} /> : null}
      </CardBody>
    </Card>
  );
}

function CvResult({ result }: { result: CvMatch }) {
  const removed = result.removed.map((kind) => REMOVED_LABELS[kind] ?? kind);
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <StatusChip tone={result.low_confidence ? "warning" : "success"}>
          {`Match ${result.score} out of 100`}
        </StatusChip>
      </div>
      {result.low_confidence ? (
        <Alert tone="warning" title="Low confidence">
          Check with an adviser or CASCOT before you rely on this result.
        </Alert>
      ) : null}
      {result.evidence.length > 0 ? (
        <section aria-label="Evidence from the CV" className="grid gap-2">
          <h3 className="text-headline text-label">Evidence from the CV</h3>
          <ul className="grid gap-3">
            {result.evidence.map((item) => (
              <li key={item.quote} className="border-separator border-l-2 pl-3">
                <blockquote className="text-callout">“{item.quote}”</blockquote>
                {item.point ? (
                  <p className="text-footnote text-label-secondary">{item.point}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {result.gaps.length > 0 ? (
        <section aria-label="Gaps" className="grid gap-2">
          <h3 className="text-headline text-label">Gaps</h3>
          <ul className="text-callout list-disc pl-5">
            {result.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {result.suggestions.length > 0 ? (
        <section aria-label="Suggestions" className="grid gap-2">
          <h3 className="text-headline text-label">Suggestions</h3>
          <ul className="text-callout list-disc pl-5">
            {result.suggestions.map((suggestion) => (
              <li key={suggestion}>{suggestion}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {removed.length > 0 ? (
        <p className="text-footnote text-label-secondary">
          Taken out before sending: {removed.join(", ")}.
        </p>
      ) : null}
      <p className="text-footnote text-label-secondary">{result.disclaimer}</p>
    </div>
  );
}
