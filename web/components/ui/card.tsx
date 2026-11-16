import { createElement, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The two card looks (U6.1.4). Glass for summaries and short cards; solid for dense data (tables,
 * long forms, detail panels), where glass would hurt reading. */
export const CARD_VARIANTS = {
  glass: "material-glass-thin rounded-card",
  solid: "bg-elevated rounded-card shadow-e1",
} as const;

export type CardVariant = keyof typeof CARD_VARIANTS;

/** A surface for one thing. Solid unless asked for glass. */
export function Card({
  variant = "solid",
  className,
  ...props
}: ComponentProps<"div"> & { variant?: CardVariant }) {
  return <div className={cn(CARD_VARIANTS[variant], className)} {...props} />;
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
