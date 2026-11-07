"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { useCan, useMe } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FileDrop } from "@/components/ui/file-drop";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatBytes } from "@/lib/ui/files";
import { formatUk } from "@/lib/ui/dates";

import { CHECK_TYPE, OUTCOME, RTW_STATUS, type RtwCheckType, type RtwOutcome } from "./rtw";

type Candidate = components["schemas"]["CandidateOut"];
type RtwTab = components["schemas"]["RTWTab"];
type CandidateFile = components["schemas"]["CandidateFile"];

function initials(row: Candidate): string {
  return `${row.first_name.charAt(0)}${row.last_name.charAt(0)}`.toUpperCase();
}

/** One candidate: header, then Overview, Applications, Right to Work, Documents and Sponsorship check. */
export function CandidateProfile({ candidateId }: { candidateId: string }) {
  const can = useCan();
  const mayRead = can("recruitment.candidate.read");
  const mayWrite = can("recruitment.candidate.write");
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void attempt((c) =>
      c.GET("/candidates/{candidate_id}", { params: { path: { candidate_id: candidateId } } }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setCandidate(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead, candidateId, version]);

  if (!mayRead) return <Alert tone="danger" title="Candidates are for HR and recruiters." />;
  if (problem) return <Alert tone="danger" title={problem.message} />;
  if (!candidate) return <p className="text-callout text-label-secondary">Loading candidate…</p>;

  const rtw = RTW_STATUS[candidate.rtw_status];
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center gap-4">
        <span
          aria-hidden
          className="bg-accent-tint text-accent-text text-headline grid size-14 place-items-center rounded-full font-semibold"
        >
          {initials(candidate)}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-large-title text-label break-words">
            {candidate.first_name} {candidate.last_name}
          </h1>
          <p className="text-callout text-label-secondary break-all">
            {candidate.email ?? "No email"} · {candidate.source ?? "Source not recorded"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusChip tone={rtw.tone}>{rtw.label}</StatusChip>
            {candidate.archived && <StatusChip tone="neutral">Archived</StatusChip>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="gray"
            disabled
            title="Postings and applications arrive in the next step."
          >
            Apply to posting
          </Button>
          <Button variant="gray" disabled title="Conversion to an employee comes later.">
            Convert to employee
          </Button>
        </div>
      </header>
      <Link href="/recruitment" className="text-callout text-accent-text underline">
        Back to recruitment
      </Link>

      <Tabs defaultValue="overview">
        <TabsList aria-label="Candidate">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="applications">Applications</TabsTrigger>
          <TabsTrigger value="rtw">Right to Work</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="sponsorship">Sponsorship check</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-4">
          <Card className="flex flex-col gap-3 p-5">
            <p className="text-callout">
              Right to work is checked before a candidate starts work. Record the check in the Right
              to Work tab; its status shows here.
            </p>
            <dl className="grid gap-2 text-callout sm:grid-cols-2">
              <dt className="text-label-secondary">Phone</dt>
              <dd>{candidate.phone ?? "Not recorded"}</dd>
              <dt className="text-label-secondary">Added</dt>
              <dd>{formatUk(candidate.created_at.slice(0, 10))}</dd>
            </dl>
          </Card>
        </TabsContent>

        <TabsContent value="applications" className="pt-4">
          <p className="text-callout text-label-secondary">
            Applications to postings appear here once they are set up.
          </p>
        </TabsContent>

        <TabsContent value="rtw" className="pt-4">
          <RtwPanel
            candidateId={candidateId}
            mayWrite={mayWrite}
            onChanged={() => setVersion((n) => n + 1)}
          />
        </TabsContent>

        <TabsContent value="documents" className="pt-4">
          <DocumentsPanel candidateId={candidateId} mayWrite={mayWrite} />
        </TabsContent>

        <TabsContent value="sponsorship" className="pt-4">
          <p className="text-callout text-label-secondary">
            Available after the sponsorship checker launches.
          </p>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RtwPanel({
  candidateId,
  mayWrite,
  onChanged,
}: {
  candidateId: string;
  mayWrite: boolean;
  onChanged: () => void;
}) {
  const me = useMe();
  const toast = useToast();
  const [tab, setTab] = useState<RtwTab | null>(null);
  const [version, setVersion] = useState(0);
  const [type, setType] = useState<RtwCheckType>("manual_list_a");
  const [checkDate, setCheckDate] = useState(new Date().toISOString().slice(0, 10));
  const [outcome, setOutcome] = useState<RtwOutcome>("pending");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/candidates/{candidate_id}/rtw-checks", {
        params: { path: { candidate_id: candidateId } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setTab(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [candidateId, version]);

  async function record(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!me) return;
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/candidates/{candidate_id}/rtw-checks", {
        params: { path: { candidate_id: candidateId } },
        body: {
          check_type: type,
          check_date: checkDate,
          checked_by_user_id: me.user.id,
          outcome,
          permission_expires: false,
        },
      }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    toast.show({ title: "Right to work check recorded", tone: "success" });
    setVersion((n) => n + 1);
    onChanged();
  }

  return (
    <div className="flex flex-col gap-6">
      {problem && <Alert tone="danger" title={problem.message} />}
      {tab && (
        <Card className="flex flex-col gap-2 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip tone={RTW_STATUS[tab.status].tone}>
              {RTW_STATUS[tab.status].label}
            </StatusChip>
            {tab.current ? (
              <span className="text-callout text-label-secondary">
                {CHECK_TYPE[tab.current.check_type]} · checked{" "}
                {tab.current.check_date ? formatUk(tab.current.check_date) : "date not recorded"}
                {tab.current.checker_name ? ` by ${tab.current.checker_name}` : ""}
              </span>
            ) : (
              <span className="text-callout text-label-secondary">No check recorded yet.</span>
            )}
          </div>
          {tab.follow_up_due_on && (
            <p className="text-footnote text-label-secondary">
              Follow up by {formatUk(tab.follow_up_due_on)}.
            </p>
          )}
        </Card>
      )}
      {mayWrite && (
        <form onSubmit={(e) => void record(e)} className="flex flex-col gap-4" noValidate>
          <h2 className="text-title-3 text-label font-semibold">Record a check</h2>
          <Select
            label="Check type"
            value={type}
            onChange={(e) => setType(e.target.value as RtwCheckType)}
          >
            {(Object.keys(CHECK_TYPE) as RtwCheckType[]).map((value) => (
              <option key={value} value={value}>
                {CHECK_TYPE[value]}
              </option>
            ))}
          </Select>
          <TextField
            label="Date of the check"
            type="date"
            required
            max={new Date().toISOString().slice(0, 10)}
            value={checkDate}
            onChange={(e) => setCheckDate(e.target.value)}
            error={problem?.field === "check_date" ? problem.message : undefined}
          />
          <Select
            label="Outcome"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value as RtwOutcome)}
          >
            {(Object.keys(OUTCOME) as RtwOutcome[]).map((value) => (
              <option key={value} value={value}>
                {OUTCOME[value]}
              </option>
            ))}
          </Select>
          <div>
            <Button type="submit" variant="filled" disabled={busy || !me}>
              Record check
            </Button>
          </div>
        </form>
      )}
      {tab && tab.checks.length > 0 && (
        <section aria-labelledby="rtw-history" className="flex flex-col gap-2">
          <h2 id="rtw-history" className="text-title-3 text-label font-semibold">
            History
          </h2>
          <ul className="flex flex-col gap-2">
            {tab.checks.map((check) => (
              <li
                key={check.id}
                className="border-separator flex flex-wrap justify-between gap-2 rounded-xl border p-3 text-callout"
              >
                <span>
                  {CHECK_TYPE[check.check_type]} ·{" "}
                  {check.check_date ? formatUk(check.check_date) : "no date"} ·{" "}
                  {OUTCOME[check.outcome]}
                </span>
                <span className="text-label-secondary">
                  {check.superseded_at ? "Replaced" : RTW_STATUS[check.status].label}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function DocumentsPanel({ candidateId, mayWrite }: { candidateId: string; mayWrite: boolean }) {
  const toast = useToast();
  const [files, setFiles] = useState<CandidateFile[] | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/candidates/{candidate_id}/documents", {
        params: { path: { candidate_id: candidateId } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) setFiles(result.data);
      else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [candidateId, version]);

  async function upload(list: File[]) {
    const file = list[0];
    if (!file) return;
    setBusy(true);
    setProblem(null);
    const form = new FormData();
    form.append("file", file);
    form.append("owner_type", "candidate");
    form.append("owner_id", candidateId);
    const result = await attempt((c) =>
      c.POST("/files", {
        body: { file: "", owner_type: "candidate", owner_id: candidateId },
        bodySerializer: () => form,
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({
        title: "Document uploaded. It is checked before anyone can open it.",
        tone: "success",
      });
      setVersion((n) => n + 1);
    } else setProblem(result.problem);
  }

  return (
    <div className="flex flex-col gap-4">
      {problem && <Alert tone="danger" title={problem.message} />}
      {mayWrite && (
        <FileDrop
          label="Add a document"
          description="A CV, certificate or other file. It is checked for viruses before anyone can open it."
          accept={[".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]}
          maxBytes={25 * 1024 * 1024}
          items={busy ? [{ id: "uploading", name: "Uploading", size: 0, status: "uploading" }] : []}
          onFiles={(list) => void upload(list)}
          disabled={busy}
        />
      )}
      {files === null ? (
        <p className="text-callout text-label-secondary">Loading documents…</p>
      ) : files.length === 0 ? (
        <p className="text-callout text-label-secondary">No documents yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {files.map((file) => (
            <li
              key={file.id}
              className="border-separator flex flex-wrap justify-between gap-2 rounded-xl border p-3 text-callout"
            >
              <span className="min-w-0 break-words">{file.name}</span>
              <span className="text-label-secondary">
                {formatBytes(file.size)} ·{" "}
                {file.scan_status === "clean" ? "Checked" : "Being checked"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
