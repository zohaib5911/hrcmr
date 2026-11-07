"use client";

import { UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { FormSheet } from "@/components/company/form-sheet";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import { RTW_STATUS } from "./rtw";

export type Candidate = components["schemas"]["CandidateOut"];

/** The candidates tab: add a candidate, search, and open a profile with its right-to-work status. */
export function CandidatesTab({ mayWrite }: { mayWrite: boolean }) {
  const router = useRouter();
  const [rows, setRows] = useState<Candidate[] | null>(null);
  const [search, setSearch] = useState("");
  const [version, setVersion] = useState(0);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/candidates", { params: { query: { search, limit: 100 } } })).then(
      (result) => {
        if (!active) return;
        if (result.ok) {
          setRows(result.data.items);
          setProblem(null);
        } else setProblem(result.problem);
      },
    );
    return () => {
      active = false;
    };
  }, [search, version]);

  const columns: Column<Candidate>[] = [
    {
      id: "name",
      header: "Candidate",
      primary: true,
      sortValue: (row) => `${row.last_name} ${row.first_name}`,
      cell: (row) => (
        <div className="min-w-0">
          <p className="break-words">
            {row.first_name} {row.last_name}
          </p>
          <p className="text-footnote text-label-secondary break-all">{row.email ?? "No email"}</p>
        </div>
      ),
    },
    {
      id: "source",
      header: "Source",
      cell: (row) => <span className="text-callout">{row.source ?? "Not recorded"}</span>,
    },
    {
      id: "rtw",
      header: "Right to work",
      sortValue: (row) => row.rtw_status,
      cell: (row) => (
        <StatusChip tone={RTW_STATUS[row.rtw_status].tone}>
          {RTW_STATUS[row.rtw_status].label}
        </StatusChip>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {problem && <Alert tone="danger" title={problem.message} />}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <SearchField
            label="Search candidates"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {mayWrite && (
          <Button variant="filled" onClick={() => setAdding(true)}>
            Add candidate
          </Button>
        )}
      </div>
      <DataTable
        caption="Candidates"
        columns={columns}
        rows={rows ?? []}
        getRowId={(row) => row.id}
        loading={rows === null && !problem}
        onRowOpen={(row) => router.push(`/recruitment/candidates/${row.id}`)}
        empty={
          <EmptyState
            icon={UserRound}
            title={search ? "No candidates match" : "No candidates yet"}
            description="Add a candidate to start tracking applications and their right-to-work check."
            action={
              mayWrite && !search ? (
                <Button variant="filled" onClick={() => setAdding(true)}>
                  Add candidate
                </Button>
              ) : undefined
            }
          />
        }
      />
      {adding && (
        <CandidateSheet
          onOpenChange={(open) => {
            if (!open) setAdding(false);
          }}
          onSaved={(created) => {
            setAdding(false);
            router.push(`/recruitment/candidates/${created.id}`);
            setVersion((n) => n + 1);
          }}
        />
      )}
    </div>
  );
}

function CandidateSheet({
  onOpenChange,
  onSaved,
}: {
  onOpenChange: (open: boolean) => void;
  onSaved: (created: Candidate) => void;
}) {
  const toast = useToast();
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    if (!first.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the first name.",
        field: "first_name",
      } as Problem);
    if (!last.trim())
      return setProblem({
        code: "VALIDATION_ERROR",
        message: "Enter the last name.",
        field: "last_name",
      } as Problem);
    setBusy(true);
    const result = await attempt((c) =>
      c.POST("/candidates", {
        body: {
          first_name: first.trim(),
          last_name: last.trim(),
          email: email.trim() || null,
          phone: phone.trim() || null,
          source: source.trim() || null,
        },
      }),
    );
    setBusy(false);
    if (!result.ok) return setProblem(result.problem);
    toast.show({ title: "Candidate added", tone: "success" });
    onSaved(result.data);
  }

  return (
    <FormSheet
      open
      title="Add candidate"
      description="Name and contact details. Right to work is recorded from the candidate's profile."
      onOpenChange={onOpenChange}
      onSubmit={(event) => void save(event)}
      busy={busy}
      problem={problem}
      saveLabel="Add candidate"
    >
      <fieldset disabled={busy} className="flex min-w-0 flex-col gap-4">
        <TextField
          label="First name"
          required
          maxLength={100}
          value={first}
          onChange={(e) => setFirst(e.target.value)}
          error={problem?.field === "first_name" ? problem.message : undefined}
        />
        <TextField
          label="Last name"
          required
          maxLength={100}
          value={last}
          onChange={(e) => setLast(e.target.value)}
          error={problem?.field === "last_name" ? problem.message : undefined}
        />
        <TextField
          label="Email (optional)"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={problem?.field === "email" ? problem.message : undefined}
        />
        <TextField
          label="Phone (optional)"
          maxLength={40}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <TextField
          label="Source (optional)"
          maxLength={40}
          value={source}
          onChange={(e) => setSource(e.target.value)}
          hint="For example: referral, job board, agency."
        />
      </fieldset>
    </FormSheet>
  );
}
