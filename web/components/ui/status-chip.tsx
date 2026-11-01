import { cva } from "class-variance-authority";

import { STATUSES, type StatusKey, type Tone } from "@/lib/ui/status";
import { cn } from "@/lib/utils";

const chip = cva(
  "rounded-pill text-footnote inline-flex items-center gap-1.5 px-2.5 py-0.5 font-medium whitespace-nowrap",
  {
    variants: {
      tone: {
        success: "bg-success-tint text-success",
        warning: "bg-warning-tint text-warning",
        danger: "bg-danger-tint text-danger",
        info: "bg-info-tint text-info",
        neutral: "bg-fill-secondary text-label",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

type StatusChipProps =
  | { status: StatusKey; label?: string; tone?: never; children?: never; className?: string }
  | { status?: never; tone: Tone; label?: never; children: React.ReactNode; className?: string };

/**
 * A status as a soft chip: a coloured dot AND words, never colour alone (plan 5.11).
 * Use a known `status` ("verified", "expiring", ...) or give a `tone` and the text.
 */
export function StatusChip({ status, tone, label, children, className }: StatusChipProps) {
  const known = status ? STATUSES[status] : null;
  const resolved: Tone = known?.tone ?? tone ?? "neutral";
  return (
    <span className={cn(chip({ tone: resolved }), className)}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {known ? (label ?? known.label) : children}
    </span>
  );
}
