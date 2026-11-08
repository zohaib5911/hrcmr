"use client";

import { ScanSearch } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { StatusChip } from "@/components/ui/status-chip";
import type { components } from "@/lib/api/client";
import { formatUk } from "@/lib/ui/dates";

export type Summary = components["schemas"]["SocCheckSummaryOut"];

type Props = {
  items: Summary[] | null;
  disabled: boolean;
  onOpen: (id: string) => void;
};

/** The company's saved checks, newest first. Opening one shows its answer and its report. */
export function CheckHistory({ items, disabled, onOpen }: Props) {
  if (items === null) {
    return <p className="text-callout text-label-secondary">Loading your saved checks…</p>;
  }
  if (items.length === 0) {
    return (
      <EmptyState
        icon={ScanSearch}
        title="No checks run yet"
        description="Each check you run is saved here, so you can open it again or download its report."
        headingLevel={2}
      />
    );
  }
  return (
    <section aria-labelledby="history-heading" className="grid gap-3">
      <h2 id="history-heading" className="text-headline text-label">
        Saved checks
      </h2>
      <ul className="grid gap-2">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onOpen(item.id)}
              disabled={disabled}
              className="border-separator hover:bg-fill-secondary flex w-full flex-wrap items-center justify-between gap-3 rounded-xl border p-3 text-left disabled:opacity-60"
            >
              <span className="min-w-0">
                <span className="text-callout block font-medium">
                  {item.soc_code} {item.soc_title}
                </span>
                <span className="text-footnote text-label-secondary block truncate">
                  {item.job_title} · {formatUk(item.created_at.slice(0, 10))}
                </span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <StatusChip tone={item.status === "confirmed" ? "success" : "neutral"}>
                  {item.status === "confirmed" ? "Confirmed" : "Draft"}
                </StatusChip>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
