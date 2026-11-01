import type { LucideIcon } from "lucide-react";
import { createElement, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Icon } from "./icon";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  /** One sentence: what will appear here, and what makes it appear (plan 5.8). */
  description: string;
  /** The one action that fills this screen. */
  action?: ReactNode;
  /** The heading level that fits the page outline. */
  headingLevel?: 2 | 3 | 4;
  className?: string;
}

/** A line icon in a soft 64 px circle, a title, one sentence and one action. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  headingLevel = 2,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}>
      <div className="bg-fill-secondary text-label-secondary rounded-pill grid size-16 place-items-center">
        <Icon icon={icon} size={24} />
      </div>
      {createElement(`h${headingLevel}`, { className: "text-title-3 text-label" }, title)}
      <p className="text-body text-label-secondary max-w-sm">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
