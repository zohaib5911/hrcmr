import type { ReactNode } from "react";

import { formatUkDateTime } from "@/lib/ui/dates";
import type { Tone } from "@/lib/ui/status";
import { cn } from "@/lib/utils";

export interface TimelineItem {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  /** An instant, as the API sends it ("2026-11-01T09:05:00Z"). Shown in UK time. */
  at: string;
  tone?: Tone;
}

const DOTS: Record<Tone, string> = {
  success: "bg-success-fill",
  warning: "bg-warning-fill",
  danger: "bg-danger-fill",
  info: "bg-info-fill",
  neutral: "bg-label-tertiary",
};

/** History, audit and application stages: newest first as given, each with its time. */
export function Timeline({
  items,
  className,
}: {
  items: readonly TimelineItem[];
  className?: string;
}) {
  return (
    <ol className={cn("flex flex-col", className)}>
      {items.map((item, index) => (
        <li key={item.id} className="relative flex gap-4 pb-6 last:pb-0">
          {index < items.length - 1 ? (
            <span
              aria-hidden="true"
              className="bg-separator absolute top-4 bottom-0 left-[5px] w-px"
            />
          ) : null}
          <span
            aria-hidden="true"
            className={cn(
              "relative mt-1.5 size-[11px] shrink-0 rounded-full",
              DOTS[item.tone ?? "neutral"],
            )}
          />
          <div className="min-w-0">
            <p className="text-callout text-label">{item.title}</p>
            {item.description ? (
              <p className="text-subheadline text-label-secondary">{item.description}</p>
            ) : null}
            <time dateTime={item.at} className="text-footnote text-label-secondary">
              {formatUkDateTime(item.at)}
            </time>
          </div>
        </li>
      ))}
    </ol>
  );
}
