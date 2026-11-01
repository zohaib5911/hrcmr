"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { Grabber, Overlay } from "./dialog";
import { Icon } from "./icon";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

type SheetContentProps = Omit<ComponentProps<typeof DialogPrimitive.Content>, "title"> & {
  title: string;
  description?: string;
  footer?: ReactNode;
  /** Which edge it slides from on screens 768 px and wider. Phones always get a bottom sheet. */
  side?: "right" | "left";
};

/**
 * The inspector drawer (plan 5.6): 440 px wide on the right, for previewing a record without losing
 * your place in the list. A bottom sheet on phones. Focus is trapped; Esc closes.
 */
export function SheetContent({
  title,
  description,
  footer,
  side = "right",
  className,
  children,
  ...props
}: SheetContentProps) {
  return (
    <DialogPrimitive.Portal>
      <Overlay />
      <DialogPrimitive.Content
        className={cn(
          "material-sheet text-label shadow-e3 fixed z-50 flex flex-col outline-none",
          "max-md:inset-x-0 max-md:bottom-0 max-md:max-h-[85dvh] max-md:rounded-t-sheet max-md:px-5 max-md:pt-3 max-md:pb-[max(1.25rem,env(safe-area-inset-bottom))]",
          "max-md:data-[state=open]:slide-in-from-bottom max-md:data-[state=closed]:slide-out-to-bottom",
          "md:inset-y-0 md:w-[440px] md:max-w-[calc(100vw-2rem)] md:p-6",
          side === "right"
            ? "md:right-0 md:rounded-l-sheet md:data-[state=open]:slide-in-from-right md:data-[state=closed]:slide-out-to-right"
            : "md:left-0 md:rounded-r-sheet md:data-[state=open]:slide-in-from-left md:data-[state=closed]:slide-out-to-left",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0",
          "duration-[var(--duration-sheet)] motion-reduce:data-[state=open]:slide-in-from-right-0 motion-reduce:data-[state=closed]:slide-out-to-right-0 motion-reduce:data-[state=open]:slide-in-from-left-0 motion-reduce:data-[state=closed]:slide-out-to-left-0 motion-reduce:max-md:data-[state=open]:slide-in-from-bottom-0 motion-reduce:max-md:data-[state=closed]:slide-out-to-bottom-0",
          className,
        )}
        {...props}
      >
        <Grabber />
        <div className="flex items-start justify-between gap-4">
          <DialogPrimitive.Title className="text-title-2 text-label">{title}</DialogPrimitive.Title>
          <DialogPrimitive.Close asChild>
            <IconButton label="Close" size="sm" className="-mt-1 -mr-2">
              <Icon icon={X} size={20} />
            </IconButton>
          </DialogPrimitive.Close>
        </div>
        {description ? (
          <DialogPrimitive.Description className="text-callout text-label-secondary mt-1">
            {description}
          </DialogPrimitive.Description>
        ) : (
          <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        )}
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto">{children}</div>
        {footer ? (
          <div className="border-separator mt-4 flex flex-wrap justify-end gap-2 border-t pt-4">
            {footer}
          </div>
        ) : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
