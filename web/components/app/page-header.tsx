import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  /** One line saying what this page is for. */
  description?: string;
  /** The page's main action (a filled button) and at most two secondary ones, on the right. */
  actions?: ReactNode;
  className?: string;
}

/** The Large Title at the top of a page (plan 5.6): the one `<h1>`, a sentence, and the actions. */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn("flex flex-wrap items-end justify-between gap-x-6 gap-y-3 pb-6", className)}
    >
      <div className="min-w-0">
        <h1 className="text-large-title text-label">{title}</h1>
        {description ? (
          <p className="text-callout text-label-secondary mt-1 max-w-2xl">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
