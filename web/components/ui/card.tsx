import { createElement, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A surface for one thing. Soft shadow in light, a hairline in dark (plan 5.4). */
export function Card({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("bg-elevated rounded-card shadow-e1", className)} {...props} />;
}

interface CardHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** Buttons or a menu, top right. */
  actions?: ReactNode;
  headingLevel?: 2 | 3 | 4;
  className?: string;
}

export function CardHeader({
  title,
  description,
  actions,
  headingLevel = 3,
  className,
}: CardHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)}>
      <div className="min-w-0">
        {createElement(`h${headingLevel}`, { className: "text-headline text-label" }, title)}
        {description ? (
          <p className="text-subheadline text-label-secondary">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function CardBody({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("text-body px-5 py-4", className)} {...props} />;
}

export function CardFooter({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "border-separator flex items-center justify-end gap-2 border-t px-5 py-3",
        className,
      )}
      {...props}
    />
  );
}
