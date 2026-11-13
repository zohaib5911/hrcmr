import type { ComponentProps, ReactNode } from "react";

import { formatUk } from "@/lib/ui/dates";
import { cn } from "@/lib/utils";

/** Public reading frame; dense form controls and tables keep the app type scale. */
export function PublicContentFrame({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("page-marketing py-10 md:py-16", className)}>{children}</div>;
}

export function PublicLead({ className, ...props }: ComponentProps<"p">) {
  return (
    <p
      className={cn("text-lead text-label-secondary max-w-[45rem] text-pretty", className)}
      {...props}
    />
  );
}

export function PublicBody({ className, ...props }: ComponentProps<"p">) {
  return <p className={cn("text-lead text-label-secondary max-w-[45rem]", className)} {...props} />;
}

/** Display a calendar date without changing the ISO source used by links, forms or crawlers. */
export function PublicDate({ value }: { value: string | null | undefined }) {
  return value ? <time dateTime={value}>{formatUk(value)}</time> : null;
}
