"use client";

import { Briefcase } from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { SearchField } from "@/components/ui/search-field";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { TabsContent, TabsList, TabsTrigger, Tabs } from "@/components/ui/tabs";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { CandidatesTab } from "./candidates-tab";
import { PostingsTab } from "./postings-tab";
import { RequisitionSheet, type Requisition } from "./requisition-sheet";

type Summary = components["schemas"]["RecruitmentSummary"];
type Status = Requisition["status"];

const STATUS: Record<
  Status,
  { label: string; tone: "neutral" | "success" | "warning" | "info" | "danger" }
> = {
  draft: { label: "Draft", tone: "neutral" },
  open: { label: "Open", tone: "success" },
  on_hold: { label: "On hold", tone: "warning" },
  filled: { label: "Filled", tone: "info" },
  cancelled: { label: "Cancelled", tone: "danger" },
};
const PER: Record<NonNullable<Requisition["budget_per"]>, string> = {
  year: "a year",
  month: "a month",
  hour: "an hour",
};

function money(value: string | null): string {
  if (value === null) return "";
  const number = Number(value);
  return Number.isNaN(number)
    ? value
    : new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(number);
}

function budget(row: Requisition): string {
  const from = money(row.budget_from);
  const to = money(row.budget_to);
  if (!from && !to) return "Not stated";
  const range = from && to && from !== to ? `${from} to ${to}` : from || to;
  return row.budget_per ? `${range} ${PER[row.budget_per]}` : range;
}

/** The Recruitment workspace: the pipeline's intro, four counts, and the requisitions tab. */
export function RecruitmentWorkspace() {
  const can = useCan();
  const mayRead = can("recruitment.requisition.read");
  const mayWrite = can("recruitment.requisition.write");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rows, setRows] = useState<Requisition[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const [version, setVersion] = useState(0);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sheet, setSheet] = useState<Requisition | "new" | null>(null);
  const [tab, setTab] = useState("requisitions");

  useEffect(() => {
    if (!mayRead) return;
    let active = true;
    void Promise.all([
      attempt((c) => c.GET("/recruitment/summary")),
      attempt((c) =>
        c.GET("/requisitions", {
          params: { query: { search, status: status || undefined, limit: 100 } },
        }),
      ),
    ]).then(([counts, list]) => {
      if (!active) return;
      if (counts.ok) setSummary(counts.data);
      if (list.ok) {
        setRows(list.data.items);
        setTotal(list.data.total);
        setProblem(null);
      } else setProblem(list.problem);
    });
    return () => {
      active = false;
    };
  }, [mayRead, search, status, version]);

  if (!mayRead) {
    return (
      <EmptyState
        icon={Briefcase}
        title="Recruitment is for HR and recruiters"
        description="Ask an HR administrator if you need to see requisitions or candidates."
      />
    );
  }

  const columns: Column<Requisition>[] = [
    {
      id: "title",
      header: "Job title",
      primary: true,
      sortValue: (row) => row.job_title,
      cell: (row) => (
        <div className="max-w-72 min-w-0">
          <p className="break-words">{row.job_title}</p>
          <p className="text-footnote text-label-secondary">
            {row.department ?? "No department"} · {row.headcount}{" "}
            {row.headcount === 1 ? "role" : "roles"}
          </p>
        </div>
      ),
    },
    {
      id: "budget",
      header: "Budget",
      cell: (row) => <span className="text-callout">{budget(row)}</span>,
    },
    {
      id: "status",
      header: "Status",
      sortValue: (row) => row.status,
      cell: (row) => (
        <StatusChip tone={STATUS[row.status].tone}>{STATUS[row.status].label}</StatusChip>
      ),
    },
    {
      id: "approved",
      header: "Approval",
      cell: (row) =>
        row.approved_at ? (
          <span className="text-callout">
            Approved {formatUk(row.approved_at.slice(0, 10))}
            {row.approved_by_name ? ` by ${row.approved_by_name}` : ""}
          </span>
        ) : (
          <span className="text-callout text-label-secondary">Not approved</span>
        ),
    },
  ];

  const counts = summary;
  return (
    <>
      <PageHeader
        title="Recruitment"
        description="Requisition, then approval, then a posting, then candidates and applications. A role opens only once it is approved."
        actions={
          mayWrite ? (
            <Button variant="filled" onClick={() => setSheet("new")}>
              New requisition
            </Button>
          ) : undefined
        }
      />
      {problem && <Alert tone="danger" title={problem.message} />}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Open requisitions" value={counts?.open_requisitions ?? 0} />
        <KpiCard label="Live postings" value={counts?.live_postings ?? 0} />
        <KpiCard label="Candidates" value={counts?.candidates ?? 0} />
        <KpiCard label="Applications in progress" value={counts?.applications_in_progress ?? 0} />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Recruitment">
          <TabsTrigger value="requisitions">
            Requisitions ({counts?.requisitions ?? total})
          </TabsTrigger>
          <TabsTrigger value="postings">Postings ({counts?.postings ?? 0})</TabsTrigger>
          <TabsTrigger value="candidates">Candidates ({counts?.candidates ?? 0})</TabsTrigger>
          <TabsTrigger value="applications">
            Applications ({counts?.applications_in_progress ?? 0})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="requisitions" className="flex flex-col gap-4 pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-64 flex-1">
              <SearchField
                label="Search requisitions"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="w-56">
              <Select
                label="Status"
                value={status}
                onChange={(e) => setStatus(e.target.value as Status | "")}
              >
                <option value="">All statuses</option>
                {(Object.keys(STATUS) as Status[]).map((value) => (
                  <option key={value} value={value}>
                    {STATUS[value].label}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <DataTable
            caption="Requisitions"
            columns={columns}
            rows={rows ?? []}
            getRowId={(row) => row.id}
            loading={rows === null && !problem}
            onRowOpen={(row) => setSheet(row)}
            empty={
              <EmptyState
                icon={Briefcase}
                title={search || status ? "No requisitions match" : "No requisitions yet"}
                description="A requisition describes a role you want to fill. It needs approval before it can open."
                action={
                  mayWrite && !search && !status ? (
                    <Button variant="filled" onClick={() => setSheet("new")}>
                      New requisition
                    </Button>
                  ) : undefined
                }
              />
            }
          />
        </TabsContent>

        <TabsContent value="postings" className="pt-4">
          <PostingsTab mayWrite={can("recruitment.posting.write")} />
        </TabsContent>

        <TabsContent value="candidates" className="pt-4">
          <CandidatesTab mayWrite={can("recruitment.candidate.write")} />
        </TabsContent>

        {(["applications"] as const).map((name) => (
          <TabsContent key={name} value={name} className="pt-4">
            <EmptyState
              icon={Briefcase}
              title="Not set up yet"
              description="Postings, candidates and applications are added to this workspace in the next steps. Your requisitions are already here."
            />
          </TabsContent>
        ))}
      </Tabs>

      {sheet && (
        <RequisitionSheet
          item={sheet === "new" ? null : sheet}
          onOpenChange={(open) => {
            if (!open) setSheet(null);
          }}
          onSaved={() => {
            setSheet(null);
            setVersion((n) => n + 1);
          }}
        />
      )}
    </>
  );
}
