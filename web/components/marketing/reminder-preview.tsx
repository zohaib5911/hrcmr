import { BadgeCheck, FileText, Plane } from "lucide-react";

import { CARD_VARIANTS } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusChip } from "@/components/ui/status-chip";
import { cn } from "@/lib/utils";

const ROWS = [
  {
    icon: BadgeCheck,
    title: "Right to Work follow-up check",
    detail: "Time-limited permission",
    due: "Due in 6 days",
    tone: "warning",
  },
  {
    icon: Plane,
    title: "Visa expiry",
    detail: "Skilled Worker",
    due: "In 28 days",
    tone: "info",
  },
  {
    icon: FileText,
    title: "Report a change of job",
    detail: "Sponsor reporting duty",
    due: "Within 10 working days",
    tone: "danger",
  },
] as const;

/** What the reminders look like in the product, as an illustration (U6.1.8). Not live data. */
export function ReminderPreview() {
  return (
    <figure className={cn(CARD_VARIANTS.glass, "p-2")}>
      <figcaption className="text-caption text-label-secondary px-3 pt-2 pb-1 font-medium tracking-wider uppercase">
        Example reminders, soonest first
      </figcaption>
      <ul className="divide-separator divide-y">
        {ROWS.map((row) => (
          <li key={row.title} className="flex items-center gap-3 px-3 py-3">
            <span className="bg-accent-tint text-accent-text grid size-9 shrink-0 place-items-center rounded-full">
              <Icon icon={row.icon} size={16} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-callout text-label font-medium">{row.title}</p>
              <p className="text-footnote text-label-secondary">{row.detail}</p>
            </div>
            <StatusChip tone={row.tone}>{row.due}</StatusChip>
          </li>
        ))}
      </ul>
    </figure>
  );
}
