import { cva } from "class-variance-authority";
import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { Icon } from "./icon";

const alert = cva("rounded-card flex gap-3 p-4", {
  variants: {
    tone: {
      info: "bg-info-tint",
      success: "bg-success-tint",
      warning: "bg-warning-tint",
      danger: "bg-danger-tint",
    },
  },
  defaultVariants: { tone: "info" },
});

const GLYPHS = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleAlert,
} as const;
const ICON_COLOURS = {
  info: "text-info",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
} as const;

interface AlertProps {
  tone?: keyof typeof GLYPHS;
  title: string;
  children?: ReactNode;
  /** A button or link that deals with it. Use a gray or filled button: a tinted one lacks contrast on a coloured banner. */
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
}

/** A banner inside the page. Warnings and errors interrupt screen readers; the rest wait their turn. */
export function Alert({
  tone = "info",
  title,
  children,
  action,
  onDismiss,
  className,
}: AlertProps) {
  return (
    <div
      role={tone === "danger" || tone === "warning" ? "alert" : "status"}
      className={cn(alert({ tone }), className)}
    >
      <Icon icon={GLYPHS[tone]} className={cn("mt-0.5", ICON_COLOURS[tone])} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-headline text-label">{title}</p>
        {children ? <div className="text-callout text-label">{children}</div> : null}
        {action ? <div className="mt-2 flex flex-wrap gap-2">{action}</div> : null}
      </div>
      {onDismiss ? (
        <IconButton label="Dismiss" size="sm" onClick={onDismiss} className="-m-1.5 self-start">
          <Icon icon={X} size={16} />
        </IconButton>
      ) : null}
    </div>
  );
}
