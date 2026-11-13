import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Icon } from "./icon";

interface GroupedListProps {
  /** A small-caps caption above the group. */
  heading: string;
  /** One sentence under the caption: what this group is. */
  description?: string;
  children: ReactNode;
  className?: string;
}

/** The inset grouped list used by the settings pages (plan 5.7): a rounded block of rows with inset hairlines between. */
export function GroupedList({ heading, description, children, className }: GroupedListProps) {
  return (
    <section aria-label={heading} className={cn("flex flex-col gap-2", className)}>
      <h2 className="text-caption text-label-secondary px-4 font-medium tracking-wider uppercase">
        {heading}
      </h2>
      {description ? <p className="text-callout text-label-secondary px-4">{description}</p> : null}
      <ul className="bg-elevated rounded-card shadow-e1 grouped-rows overflow-hidden">
        {children}
      </ul>
    </section>
  );
}

interface GroupedRowProps {
  title: string;
  /** What is set, in a few words, or a count. Shown on the right. */
  detail?: ReactNode;
  icon?: ReactNode;
  /** A page to open. Give this or `onClick`; with neither the row only shows what is set. */
  href?: string;
  onClick?: () => void;
}

const ROW =
  "flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left transition-colors motion-micro hover:bg-fill-secondary " +
  "focus-visible:outline-accent focus-visible:outline-2 focus-visible:-outline-offset-2 outline-none";

/** One row: an icon, a title, what it holds, and a chevron. A whole row is the link or the button. */
export function GroupedRow({ title, detail, icon, href, onClick }: GroupedRowProps) {
  const interactive = href !== undefined || onClick !== undefined;
  const content = (
    <>
      {icon ? <span className="text-label-secondary flex shrink-0">{icon}</span> : null}
      <span className="text-body text-label min-w-0 flex-1 break-words">{title}</span>
      {detail ? (
        <span className="text-callout text-label-secondary max-w-[50%] text-right break-words tabular-nums">
          {detail}
        </span>
      ) : null}
      {interactive ? <Icon icon={ChevronRight} size={16} className="text-label-tertiary" /> : null}
    </>
  );
  if (!interactive) {
    return <li className="flex min-h-14 items-center gap-3 px-4 py-3">{content}</li>;
  }
  return (
    <li>
      {href ? (
        <Link href={href as Route} className={ROW}>
          {content}
        </Link>
      ) : (
        <button type="button" onClick={onClick} className={cn(ROW, "cursor-pointer")}>
          {content}
        </button>
      )}
    </li>
  );
}

/** A row that says nothing is here yet, with the action that adds it. */
export function GroupedEmpty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <li className="flex min-h-14 flex-wrap items-center justify-between gap-3 px-4 py-3">
      <span className="text-body text-label-secondary">{children}</span>
      {action}
    </li>
  );
}
