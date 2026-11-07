"use client";

import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";

import type { OrgPerson, Row } from "./layout";

const dash = "—";
// Literal class names, so Tailwind keeps them. Deeper levels stop indenting at the last one.
const INDENT = ["pl-0", "pl-4", "pl-8", "pl-12", "pl-16", "pl-20", "pl-24", "pl-28", "pl-32"];

/** The chart as a table: indented by depth, so the reporting lines still read top to bottom. */
export function OrgList({
  rows,
  rtwVisible,
  onOpen,
}: {
  rows: readonly Row[];
  rtwVisible: boolean;
  onOpen: (person: OrgPerson) => void;
}) {
  const columns: Column<Row>[] = [
    {
      id: "name",
      header: "Name",
      primary: true,
      cell: (row) => (
        <span
          className={`font-semibold ${INDENT[Math.min(row.depth, INDENT.length - 1)] ?? "pl-0"}`}
        >
          {row.person.name}
        </span>
      ),
    },
    { id: "job_title", header: "Job title", cell: (row) => row.person.job_title ?? dash },
    { id: "department", header: "Department", cell: (row) => row.person.department ?? dash },
    { id: "level", header: "Level", cell: (row) => row.person.level ?? dash },
    {
      id: "reports",
      header: "Direct reports",
      align: "end",
      cell: (row) => row.person.reports.length,
    },
  ];
  if (rtwVisible) {
    columns.push({
      id: "rtw",
      header: "Right to work",
      cell: (row) => (row.person.rtw_status ? row.person.rtw_status.replace(/_/g, " ") : dash),
    });
  }
  columns.push({
    id: "open",
    header: "Open",
    cell: (row) => (
      <Button
        variant="gray"
        size="sm"
        aria-label={`Open ${row.person.name}`}
        onClick={() => onOpen(row.person)}
      >
        Open
      </Button>
    ),
  });
  return (
    <DataTable
      caption="People in the org chart"
      columns={columns}
      rows={rows}
      getRowId={(row) => row.person.id}
      onRowOpen={(row) => onOpen(row.person)}
    />
  );
}
