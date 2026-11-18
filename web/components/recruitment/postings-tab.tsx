"use client";

import { Megaphone } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { attempt, type Problem } from "@/lib/auth/request";
import { formatUk } from "@/lib/ui/dates";

import { PostingSheet, type Posting } from "./posting-sheet";
import { cacheKey, cached, remember } from "@/lib/api/cache";

type Status = Posting["status"];

const STATUS: Record<Status, { label: string; tone: "neutral" | "success" | "danger" }> = {
  draft: { label: "Draft", tone: "neutral" },
  open: { label: "Open", tone: "success" },
  closed: { label: "Closed", tone: "danger" },
};

/** The Postings tab: each posting's visibility, closing date, vacancies, status and public link. */
export function PostingsTab({ mayWrite }: { mayWrite: boolean }) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  // O6.1.6: this query's answer once in; until then the last one this tab had.
  const key = cacheKey("/postings", { search, status: status || undefined, limit: 100 });
  const [answer, setAnswer] = useState<{ key: string; items: Posting[] } | null>(null);
  const rows =
    answer?.key === key ? answer.items : (cached<{ items: Posting[] }>(key)?.items ?? null);
  const [version, setVersion] = useState(0);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sheet, setSheet] = useState<Posting | "new" | null>(null);

  useEffect(() => {
    let active = true;
    void attempt((c) =>
      c.GET("/postings", {
        params: { query: { search, status: status || undefined, limit: 100 } },
      }),
    ).then((result) => {
      if (!active) return;
      if (result.ok) {
        remember(key, result.data);
        setAnswer({ key, items: result.data.items });
        setProblem(null);
      } else setProblem(result.problem);
    });
    return () => {
      active = false;
    };
  }, [key, search, status, version]);

  async function copy(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      toast.show({ title: "Public link copied", tone: "success" });
    } catch {
      setProblem({
        code: "COPY_FAILED",
        message: "Select the link and copy it yourself.",
      } as Problem);
    }
  }

  const columns: Column<Posting>[] = [
    {
      id: "posting",
      header: "Posting",
      primary: true,
      sortValue: (row) => row.title,
      cell: (row) => (
        <div className="max-w-72 min-w-0">
          <p className="break-words">{row.title}</p>
          <p className="text-footnote text-label-secondary">{row.requisition_title}</p>
        </div>
      ),
    },
    {
      id: "visibility",
      header: "Visibility",
      cell: (row) => (row.visibility === "external" ? "External" : "Internal"),
    },
    {
      id: "closes",
      header: "Closes",
      sortValue: (row) => row.closes_on ?? "",
      cell: (row) => (row.closes_on ? formatUk(row.closes_on) : "Not set"),
    },
    {
      id: "vacancies",
      header: "Vacancies",
      sortValue: (row) => row.vacancies,
      cell: (row) => row.vacancies,
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
      id: "link",
      header: "Public link",
      cell: (row) =>
        row.public_link ? (
          <Button
            type="button"
            variant="gray"
            size="sm"
            onClick={() => void copy(row.public_link ?? "")}
          >
            Copy link
          </Button>
        ) : (
          <span className="text-callout text-label-secondary">None</span>
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {problem && <Alert tone="danger" title={problem.message} />}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <SearchField
            label="Search postings"
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
        {mayWrite && (
          <Button variant="filled" onClick={() => setSheet("new")}>
            New posting
          </Button>
        )}
      </div>
      <DataTable
        caption="Postings"
        columns={columns}
        rows={rows ?? []}
        getRowId={(row) => row.id}
        loading={rows === null && !problem}
        onRowOpen={(row) => setSheet(row)}
        empty={
          <EmptyState
            icon={Megaphone}
            title={search || status ? "No postings match" : "No postings yet"}
            description="A posting advertises an open requisition. Set one up once a requisition is approved."
          />
        }
      />
      {sheet && (
        <PostingSheet
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
    </div>
  );
}
