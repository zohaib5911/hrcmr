"use client";

import { Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import { PipelineBar } from "./pipeline-bar";
import { RTW_STATUS } from "./rtw";
import { STAGE_LABEL, STAGE_TONE, type Stage } from "./stages";

type Application = components["schemas"]["ApplicationOut"];

/** The Applications tab: the pipeline bar with counts, then the applications at the chosen stage. */
export function ApplicationsTab() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage | null>(null);
  const [counts, setCounts] = useState<Partial<Record<Stage, number>>>({});
  const [rows, setRows] = useState<Application[] | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) => c.GET("/recruitment/pipeline")).then((result) => {
      if (!active || !result.ok) return;
      setCounts(Object.fromEntries(result.data.stages.map((item) => [item.stage, item.count])));
    });
    void attempt((c) =>
      c.GET("/applications", { params: { query: { stage: stage ?? undefined, limit: 100 } } }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) {
        setRows(result.data.items);
        setProblem(null);
      } else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [stage]);

  const columns: Column<Application>[] = [
    {
      id: "candidate",
      header: "Candidate",
      primary: true,
      sortValue: (row) => row.candidate_name,
      cell: (row) => <span className="break-words">{row.candidate_name}</span>,
    },
    {
      id: "posting",
      header: "Posting",
      cell: (row) => <span className="break-words">{row.posting_title}</span>,
    },
    {
      id: "stage",
      header: "Stage",
      sortValue: (row) => row.stage,
      cell: (row) => <StatusChip tone={STAGE_TONE[row.stage]}>{STAGE_LABEL[row.stage]}</StatusChip>,
    },
    {
      id: "rtw",
      header: "Right to work",
      cell: (row) => (
        <StatusChip tone={RTW_STATUS[row.candidate_rtw_status].tone}>
          {RTW_STATUS[row.candidate_rtw_status].label}
        </StatusChip>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PipelineBar counts={counts} selected={stage} onSelect={setStage} />
      {problem && <Alert tone="danger" title={problem.message} />}
      <DataTable
        caption="Applications"
        columns={columns}
        rows={rows ?? []}
        getRowId={(row) => row.id}
        loading={rows === null && !problem}
        onRowOpen={(row) => router.push(`/recruitment/applications/${row.id}`)}
        empty={
          <EmptyState
            icon={Users}
            title={stage ? "No applications at this stage" : "No applications yet"}
            description="An application links a candidate to an open posting. Add one from a candidate's profile."
          />
        }
      />
    </div>
  );
}
