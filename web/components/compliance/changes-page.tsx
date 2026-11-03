"use client";

import { ClipboardList } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import {
  ArchiveChangeSheet,
  EmployeeChangeSheet,
  OrgChangeSheet,
  ReportedSheet,
  ReportingSources,
} from "@/components/compliance/change-forms";
import { ChangeSummary } from "@/components/compliance/change-log";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchField } from "@/components/ui/search-field";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { StatusChip } from "@/components/ui/status-chip";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  CHANGE_FILTERS,
  changeLabel,
  STATUS,
  type ChangeFilter,
  type Change,
  type OrgChange,
  type Reporting,
} from "@/lib/compliance/changes";
import { shortDate } from "@/lib/employees/profile";

type Dialog =
  | { kind: "employee" }
  | { kind: "org"; record: OrgChange | null }
  | { kind: "archive"; record: OrgChange }
  | { kind: "inspect" | "report"; record: Reporting };
const columns: Column<Reporting>[] = [
  {
    id: "change",
    header: "Change",
    primary: true,
    sortValue: (r) => changeLabel(r),
    cell: (r) => (
      <div className="min-w-0">
        <p className="text-body text-label break-words">{changeLabel(r)}</p>
        {"employee_id" in r && (
          <p className="text-footnote text-label-secondary">
            {r.employee_name} · {r.employee_number}
          </p>
        )}
      </div>
    ),
  },
  {
    id: "date",
    header: "Event / awareness date",
    sortValue: (r) => r.change_date,
    cell: (r) => shortDate(r.change_date),
  },
  {
    id: "deadline",
    header: "Reporting deadline",
    sortValue: (r) => r.deadline_date,
    cell: (r) => (r.deadline_date ? shortDate(r.deadline_date) : "Report promptly"),
  },
  {
    id: "status",
    header: "Status",
    sortValue: (r) => r.status,
    exportValue: (r) => STATUS[r.status].label,
    cell: (r) => <StatusChip tone={STATUS[r.status].tone}>{STATUS[r.status].label}</StatusChip>,
  },
];

export function ChangesPage({
  changes,
  organisation,
}: {
  changes: Change[];
  organisation: OrgChange[];
}) {
  const can = useCan();
  const router = useRouter();
  const [tab, setTab] = useState("workers");
  const [filter, setFilter] = useState<ChangeFilter>("all");
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const mayWrite = can("employee.change_of_circumstances.write");
  const rows: Reporting[] = tab === "workers" ? changes : organisation;
  const shown = rows.filter(
    (row) =>
      (filter === "all" ||
        (filter === "unreported" ? !row.reported_at : row.status === "overdue")) &&
      search
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean)
        .every((word) =>
          (
            changeLabel(row) +
            ("employee_id" in row ? " " + row.employee_name + " " + row.employee_number : "") +
            " " +
            (row.reported_reference ?? "")
          )
            .toLowerCase()
            .includes(word),
        ),
  );
  const inspected =
    dialog?.kind === "inspect"
      ? ([...changes, ...organisation].find((row) => row.id === dialog.record.id) ?? dialog.record)
      : null;
  const saved = () => router.refresh();
  return (
    <>
      <PageHeader
        title="Change of circumstances"
        description="Worker and organisation reporting records, deadlines and reports made in SMS."
        actions={
          mayWrite ? (
            <Button
              onClick={() =>
                setDialog(tab === "workers" ? { kind: "employee" } : { kind: "org", record: null })
              }
            >
              {tab === "workers" ? "Log employee change" : "Log organisation change"}
            </Button>
          ) : null
        }
      />
      <div className="flex flex-col gap-4">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList aria-label="Change logs">
            <TabsTrigger value="workers">Workers</TabsTrigger>
            <TabsTrigger value="organisation">Organisation</TabsTrigger>
          </TabsList>
          <TabsContent value={tab} className="pt-4">
            <div className="flex flex-col gap-4">
              <div className="max-w-full overflow-x-auto">
                <SegmentedControl
                  label="Show changes"
                  value={filter}
                  onValueChange={setFilter}
                  className="min-w-max"
                  segments={CHANGE_FILTERS}
                />
              </div>
              <SearchField
                label="Search changes"
                listSearch
                containerClassName="sm:w-80"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <DataTable
                caption={tab === "workers" ? "Worker changes" : "Organisation changes"}
                columns={columns}
                rows={shown}
                getRowId={(r) => r.id}
                onRowOpen={(record) => setDialog({ kind: "inspect", record })}
                defaultSort={{ column: "deadline", direction: "asc" }}
                empty={
                  <EmptyState
                    icon={ClipboardList}
                    title={
                      filter !== "all" || search.trim() ? "No changes match" : "No changes logged"
                    }
                    description={
                      filter !== "all" || search.trim()
                        ? "Try a different search or clear the filter."
                        : "Logged changes and their reporting records will appear here."
                    }
                  />
                }
              />
            </div>
          </TabsContent>
        </Tabs>
        <ReportingSources />
      </div>
      {dialog?.kind === "employee" && (
        <EmployeeChangeSheet onClose={() => setDialog(null)} onSaved={saved} />
      )}
      {dialog?.kind === "org" && (
        <OrgChangeSheet record={dialog.record} onClose={() => setDialog(null)} onSaved={saved} />
      )}
      {dialog?.kind === "archive" && (
        <ArchiveChangeSheet
          record={dialog.record}
          onClose={() => setDialog(null)}
          onSaved={saved}
        />
      )}
      {dialog?.kind === "report" && (
        <ReportedSheet record={dialog.record} onClose={() => setDialog(null)} onSaved={saved} />
      )}
      {dialog?.kind === "inspect" && inspected && (
        <Sheet open onOpenChange={(open) => !open && setDialog(null)}>
          <SheetContent
            title="Change details"
            description={
              "employee_id" in inspected ? inspected.employee_name : "Organisation change"
            }
            readOnly
          >
            <div className="flex flex-col gap-4">
              <ChangeSummary record={inspected} />
              {"employee_id" in inspected && (
                <Button
                  variant="gray"
                  onClick={() => {
                    if ("employee_id" in inspected)
                      router.push("/employees/" + inspected.employee_id);
                  }}
                >
                  Open employee
                </Button>
              )}
              {mayWrite && !inspected.reported_at && (
                <>
                  <Button onClick={() => setDialog({ kind: "report", record: inspected })}>
                    Mark as reported
                  </Button>
                  {!("employee_id" in inspected) && (
                    <>
                      <Button
                        variant="gray"
                        onClick={() => setDialog({ kind: "org", record: inspected as OrgChange })}
                      >
                        Edit entry
                      </Button>
                      <Button
                        variant="plain"
                        onClick={() =>
                          setDialog({ kind: "archive", record: inspected as OrgChange })
                        }
                      >
                        Archive entry
                      </Button>
                    </>
                  )}
                </>
              )}
            </div>
          </SheetContent>
        </Sheet>
      )}
    </>
  );
}
