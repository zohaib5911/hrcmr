"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TextField } from "@/components/ui/text-field";
import { Toggle } from "@/components/ui/toggle";
import { useToast } from "@/components/ui/toast";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import { COLOUR_CLASS } from "@/lib/company/holidays";

import { LeaveTypeSheet } from "./type-sheet";

export type LeaveType = components["schemas"]["LeaveTypeOut"];
type Settings = components["schemas"]["LeaveSettingsOut"];

function SettingsForm({ settings, mayEdit }: { settings: Settings; mayEdit: boolean }) {
  const router = useRouter();
  const toast = useToast();
  const [start, setStart] = useState(settings.leave_year_start_month_day);
  const [negative, setNegative] = useState(settings.allow_negative_leave_balance);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem(null);
    const result = await attempt((api) =>
      api.PATCH("/leave/settings", {
        body: { leave_year_start_month_day: start, allow_negative_leave_balance: negative },
      }),
    );
    setBusy(false);
    if (result.ok) {
      toast.show({ title: "Leave settings saved", tone: "success" });
      router.refresh();
    } else setProblem(result.problem);
  }

  return (
    <form
      onSubmit={save}
      noValidate
      className="bg-elevated rounded-card shadow-e1 flex max-w-2xl flex-col gap-4 p-4"
      aria-label="Leave year and balances"
    >
      <h2 className="text-title-3 text-label">Leave year and balances</h2>
      {problem && !problem.field ? <Alert tone="danger" title={problem.message} /> : null}
      <TextField
        label="Leave year starts (MM-DD)"
        hint="For example, 01-01 or 04-06. Choose a date that occurs every year."
        value={start}
        onChange={(event) => setStart(event.target.value)}
        disabled={!mayEdit}
        error={problem?.field === "leave_year_start_month_day" ? problem.message : undefined}
      />
      <Toggle
        label="Allow negative leave balances"
        description="People may request more leave than their available balance."
        checked={negative}
        onCheckedChange={setNegative}
        disabled={!mayEdit}
      />
      {mayEdit ? (
        <div className="flex justify-end">
          <Button type="submit" loading={busy}>
            Save leave settings
          </Button>
        </div>
      ) : null}
    </form>
  );
}

export function LeaveSettingsPage({ settings, types }: { settings: Settings; types: LeaveType[] }) {
  const can = useCan();
  const mayEditTypes = can("leave.type.write");
  const [editing, setEditing] = useState<LeaveType | "new" | null>(null);
  const [guidance, setGuidance] = useState<LeaveType | null>(null);
  const columns: Column<LeaveType>[] = [
    {
      id: "name",
      header: "Name",
      primary: true,
      sortValue: (row) => row.name,
      cell: (row) => (
        <span className="inline-flex items-center gap-2">
          <span
            aria-hidden
            className={`h-2 w-2 shrink-0 rounded-full ${COLOUR_CLASS[row.colour]}`}
          />
          {mayEditTypes ? (
            <Button variant="plain" onClick={() => setEditing(row)}>
              {row.name}
            </Button>
          ) : (
            row.name
          )}
        </span>
      ),
    },
    { id: "paid", header: "Paid provision", cell: (row) => (row.is_paid ? "Yes" : "No") },
    {
      id: "statutory",
      header: "Counts toward statutory minimum",
      cell: (row) => (row.counts_toward_statutory ? "Yes" : "No"),
    },
    {
      id: "days",
      header: "Days a year",
      align: "end",
      cell: (row) =>
        row.days_per_year === null
          ? "No fixed allowance"
          : Number(row.days_per_year).toLocaleString("en-GB"),
      sortValue: (row) => (row.days_per_year === null ? null : Number(row.days_per_year)),
    },
    {
      id: "carry",
      header: "Carry-over limit",
      align: "end",
      cell: (row) => `${Number(row.carry_over_limit_days).toLocaleString("en-GB")} days`,
    },
    {
      id: "guidance",
      header: "Guidance",
      cell: (row) => (
        <Button
          variant="plain"
          onClick={() => setGuidance(row)}
          aria-label={`Guidance for ${row.name}`}
        >
          View guidance
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Leave settings"
        description="Your leave year, balance policy and leave types."
        actions={
          <Button asChild variant="gray">
            <Link href="/leave">Leave</Link>
          </Button>
        }
      />
      <div className="flex flex-col gap-8">
        <SettingsForm settings={settings} mayEdit={can("leave.config.write")} />
        <section aria-labelledby="leave-types-heading" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="leave-types-heading" className="text-title-3 text-label">
              Leave types
            </h2>
            {mayEditTypes ? (
              <Button onClick={() => setEditing("new")}>Add leave type</Button>
            ) : null}
          </div>
          <p className="text-footnote text-label-secondary">
            Paid provision depends on eligibility and does not guarantee full salary throughout the
            leave. No fixed allowance means entitlement follows the applicable rules. Annual leave
            includes bank holidays.
          </p>
          <DataTable
            caption="Leave types"
            rows={types}
            columns={columns}
            getRowId={(row) => row.id}
            onRowOpen={(row) => (mayEditTypes ? setEditing(row) : setGuidance(row))}
            pageSize={20}
          />
        </section>
      </div>
      {editing ? (
        <LeaveTypeSheet
          key={editing === "new" ? "new" : editing.id}
          item={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
      {guidance ? (
        <Sheet open onOpenChange={(open) => !open && setGuidance(null)}>
          <SheetContent title={`${guidance.name} guidance`} readOnly>
            <p className="text-body text-label">
              {guidance.rule_text || "No guidance has been added for this company leave type."}
            </p>
            {guidance.source_url ? (
              <p className="text-footnote text-label-secondary mt-4">
                Seed guidance checked {guidance.checked_on}.{" "}
                <a
                  href={guidance.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent-text underline"
                >
                  GOV.UK source
                </a>
                . Company policy edits may differ from this original reference.
              </p>
            ) : null}
          </SheetContent>
        </Sheet>
      ) : null}
    </>
  );
}
