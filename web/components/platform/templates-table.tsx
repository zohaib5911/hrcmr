"use client";

import { FileText } from "lucide-react";

import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { formatUk } from "@/lib/ui/dates";
import type { TemplateEntry } from "@/lib/templates/manifest";

const COLUMNS: readonly Column<TemplateEntry>[] = [
  {
    id: "title",
    header: "Title",
    primary: true,
    sortValue: (t) => t.title,
    cell: (t) => (
      <span className="flex min-w-0 flex-col">
        <span className="text-body text-label">{t.title}</span>
        <span className="text-footnote text-label-secondary">{t.description}</span>
      </span>
    ),
  },
  { id: "file", header: "File", sortValue: (t) => t.file, cell: (t) => t.file },
  { id: "version", header: "Version", sortValue: (t) => t.version, cell: (t) => t.version },
  {
    id: "reviewed",
    header: "Reviewed on",
    sortValue: (t) => t.reviewed_on,
    cell: (t) => (t.reviewed_on ? formatUk(t.reviewed_on) : "Not yet reviewed"),
  },
];

/** The repository template manifest as a table; one card per template on phones. */
export function TemplatesTable({ templates }: { templates: readonly TemplateEntry[] }) {
  return (
    <DataTable
      caption="Templates"
      columns={COLUMNS}
      rows={templates}
      getRowId={(t) => t.slug}
      pageSize={50}
      empty={
        <EmptyState
          icon={FileText}
          title="No templates"
          description="Templates appear here once they are added to the repository manifest."
        />
      }
    />
  );
}
