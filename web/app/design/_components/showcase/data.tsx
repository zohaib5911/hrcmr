"use client";

import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Avatar, AvatarStack } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { CalendarMonth, type DayMarker } from "@/components/ui/calendar-month";
import { Card, CardBody, CardFooter, CardHeader } from "@/components/ui/card";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { MenuItem } from "@/components/ui/menu";
import { StatusChip } from "@/components/ui/status-chip";
import { Timeline } from "@/components/ui/timeline";
import { useToast } from "@/components/ui/toast";
import { formatUk } from "@/lib/ui/dates";
import { toCsv } from "@/lib/ui/csv";
import { formatNumber } from "@/lib/ui/numbers";
import { STATUSES, type StatusKey } from "@/lib/ui/status";

import { demoPeople, type DemoPerson } from "../demo-data";
import { Demo, DocSection, State } from "./doc";

const COLUMNS: Column<DemoPerson>[] = [
  {
    id: "name",
    header: "Name",
    primary: true,
    sortValue: (p) => p.name,
    cell: (p) => (
      <span className="flex items-center gap-3">
        <Avatar name={p.name} size="sm" decorative />
        <span className="font-medium">{p.name}</span>
      </span>
    ),
  },
  {
    id: "department",
    header: "Department",
    sortValue: (p) => p.department,
    cell: (p) => p.department,
  },
  {
    id: "role",
    header: "Role",
    sortValue: (p) => p.role,
    cell: (p) => p.role,
    defaultHidden: true,
  },
  {
    id: "status",
    header: "Right to Work",
    sortValue: (p) => STATUSES[p.status as StatusKey].label,
    cell: (p) => <StatusChip status={p.status} />,
  },
  { id: "start", header: "Start date", sortValue: (p) => p.start, cell: (p) => formatUk(p.start) },
  {
    id: "salary",
    header: "Salary",
    align: "end",
    sortValue: (p) => p.salary,
    cell: (p) => `£${formatNumber(p.salary, 0)}`,
  },
];

const MARKERS: ReadonlyMap<string, DayMarker> = new Map([
  ["2026-11-05", { label: "Leave: Ada Lovelace", tone: "success" }],
  ["2026-11-12", { label: "Right to Work check due", tone: "warning" }],
  ["2026-11-20", { label: "Report deadline", tone: "danger" }],
  ["2026-12-25", { label: "Bank holiday", tone: "info" }],
]);

const PEOPLE = [
  "Ada Lovelace",
  "Grace Hopper",
  "Alan Turing",
  "Katherine Johnson",
  "Tim Berners",
  "Margaret Hamilton",
];

export function DataSection() {
  const toast = useToast();
  const small = useMemo(() => demoPeople(12), []);
  const large = useMemo(() => demoPeople(1000), []);
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState("2026-11-01");
  const [chosen, setChosen] = useState<string | null>(null);

  const open = (person: DemoPerson) => toast.show({ title: `Opened ${person.name}` });
  const exportRows = (rows: readonly DemoPerson[], columns: readonly Column<DemoPerson>[]) => {
    const csv = toCsv(
      columns.map((c) => c.header),
      rows.map((row) => columns.map((c) => (c.exportValue ?? c.sortValue)?.(row) ?? "")),
    );
    toast.show({
      title: "Export ready",
      description: `${rows.length} rows, ${csv.length.toLocaleString("en-GB")} characters.`,
    });
  };

  return (
    <DocSection
      id="data"
      title="Data"
      description="Chips, avatars, cards, KPI numbers, timelines, a calendar and the table. Status is always words as well as colour, and numbers use tabular figures so columns line up."
    >
      <Demo title="Status chips" note="A dot and words. Colour is never the only signal.">
        {(Object.keys(STATUSES) as StatusKey[]).map((key) => (
          <StatusChip key={key} status={key} />
        ))}
      </Demo>

      <Demo
        title="Avatars"
        note="Initials on a soft colour that is the same for the same person every time."
      >
        <div className="flex items-end gap-3">
          <Avatar name="Ada Lovelace" size="xs" />
          <Avatar name="Grace Hopper" size="sm" />
          <Avatar name="Alan Turing" size="md" />
          <Avatar name="Katherine Johnson" size="lg" />
        </div>
        <State label="Stack">
          <AvatarStack people={PEOPLE.map((name) => ({ name }))} max={4} />
        </State>
        <State label="Many names">
          <div className="flex gap-2">
            {PEOPLE.map((name) => (
              <Avatar key={name} name={name} />
            ))}
          </div>
        </State>
        <State label="Łukasz Żak, one name, empty">
          <div className="flex gap-2">
            <Avatar name="Łukasz Żak" />
            <Avatar name="Cher" />
            <Avatar name="" />
          </div>
        </State>
      </Demo>

      <Demo
        title="KPI cards"
        note="The number counts up once, the first time it is on screen, unless motion is reduced."
      >
        <div className="grid w-full gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard
            label="Employees"
            value={128}
            subLabel="3 joined this month"
            trend={[96, 102, 110, 118, 121, 128]}
            trendLabel="Up from 96 to 128 over six months."
            link={{ href: { hash: "data" }, label: "View all" }}
          />
          <KpiCard label="Checks expiring in 28 days" value={4} subLabel="Needs attention" />
          <KpiCard
            label="Leave taken this year"
            value={1284}
            format={(n) => `${n.toLocaleString("en-GB")} days`}
            subLabel="Across everyone"
          />
        </div>
      </Demo>

      <Demo title="Card">
        <Card className="w-full max-w-md">
          <CardHeader
            title="Sponsor licence"
            description="Renews on 14 Mar 2028"
            actions={<StatusChip status="verified" />}
          />
          <CardBody>
            Your licence is active, with a B rating. Report changes within 10 working days.
          </CardBody>
          <CardFooter>
            <Button variant="gray" size="sm">
              View history
            </Button>
            <Button size="sm">Report a change</Button>
          </CardFooter>
        </Card>
      </Demo>

      <Demo
        title="Timeline"
        note="History, audit and application stages, each with its time in UK time."
      >
        <div className="w-full max-w-md">
          <Timeline
            items={[
              {
                id: "1",
                title: "Right to Work check passed",
                description: "Share code verified by Ada Lovelace",
                at: "2026-11-01T09:05:00Z",
                tone: "success",
              },
              { id: "2", title: "Offer accepted", at: "2026-10-20T14:40:00Z", tone: "info" },
              {
                id: "3",
                title: "Interview scheduled",
                description: "With Grace Hopper",
                at: "2026-07-01T08:30:00Z",
              },
              { id: "4", title: "Application received", at: "2026-06-12T11:00:00Z" },
            ]}
          />
        </div>
      </Demo>

      <Demo
        title="Calendar"
        note="Arrow keys move by day and week, Home and End to the week's ends, PageUp and PageDown by month (Shift for year). Dots mark leave, deadlines and bank holidays."
      >
        <div className="bg-elevated rounded-card shadow-e1 max-w-full p-3">
          <CalendarMonth
            focused={focused}
            onFocusedChange={setFocused}
            selected={chosen}
            onSelect={setChosen}
            markers={MARKERS}
          />
        </div>
        <p className="text-callout text-label-secondary max-w-xs" aria-live="polite">
          {chosen ? `You chose ${formatUk(chosen)}.` : "Nothing chosen yet."}
        </p>
      </Demo>

      <Demo
        title="Data table"
        note="Click a header to sort. Click the table, then use J and K (or the arrows) to move, Enter to open, Space to select, . (full stop) for the row's menu. Below 768 px each row is a card."
      >
        <div className="w-full">
          <DataTable
            caption="Employees"
            columns={COLUMNS}
            rows={small}
            getRowId={(p) => p.id}
            selectable
            selected={picked}
            onSelectedChange={setPicked}
            onRowOpen={open}
            rowMenu={(person) => (
              <>
                <MenuItem onSelect={() => open(person)}>Open profile</MenuItem>
                <MenuItem onSelect={() => toast.show({ title: `Reminder set for ${person.name}` })}>
                  Set a reminder
                </MenuItem>
              </>
            )}
            onExport={exportRows}
            pageSize={5}
            defaultSort={{ column: "name", direction: "asc" }}
          />
        </div>
      </Demo>

      <Demo
        title="Data table with 1,000 rows"
        note="Over 200 rows it stops paging and draws only the rows in view, so it stays fast."
      >
        <div className="w-full">
          <DataTable
            caption="All employees"
            columns={COLUMNS}
            rows={large}
            getRowId={(p) => p.id}
            onRowOpen={open}
          />
        </div>
      </Demo>

      <Demo title="Loading and empty">
        <div className="flex w-full flex-col gap-4">
          <div className="flex gap-2">
            <Button size="sm" variant="gray" onClick={() => setLoading((v) => !v)}>
              {loading ? "Show the rows" : "Show loading"}
            </Button>
          </div>
          <DataTable
            caption="Employees (loading)"
            columns={COLUMNS}
            rows={small}
            getRowId={(p) => p.id}
            loading={loading}
            pageSize={4}
          />
          <div className="bg-elevated rounded-card shadow-e1">
            <DataTable
              caption="Employees (none)"
              columns={COLUMNS}
              rows={[]}
              getRowId={(p) => p.id}
              empty={
                <EmptyState
                  icon={Search}
                  title="No employees match"
                  description="Clear the filters, or add someone who does."
                  action={
                    <Button>
                      <Plus className="size-4" aria-hidden="true" />
                      Add an employee
                    </Button>
                  }
                  headingLevel={3}
                />
              }
            />
          </div>
        </div>
      </Demo>
    </DocSection>
  );
}
