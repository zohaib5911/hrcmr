import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** One component family on the /design page: a heading, a sentence, and its demos. */
export function DocSection({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-24 flex-col gap-6">
      <div>
        <h2 id={`${id}-title`} className="text-title-1 text-label">
          {title}
        </h2>
        <p className="text-callout text-label-secondary max-w-3xl">{description}</p>
      </div>
      {children}
    </section>
  );
}

/** One component in one or more states, on a card. */
export function Demo({
  title,
  note,
  children,
  className,
}: {
  title: string;
  note?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="bg-elevated rounded-card shadow-e1 flex flex-col gap-4 p-5">
      <div>
        <h3 className="text-headline text-label">{title}</h3>
        {note ? <p className="text-subheadline text-label-secondary">{note}</p> : null}
      </div>
      <div className={cn("flex flex-wrap items-start gap-4", className)}>{children}</div>
    </div>
  );
}

/** A small caption above one state ("Error", "Disabled"). */
export function State({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <span className="text-caption text-label-secondary font-medium tracking-wide uppercase">
        {label}
      </span>
      {children}
    </div>
  );
}
