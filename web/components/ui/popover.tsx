"use client";

import { Popover as PopoverPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;
export const PopoverClose = PopoverPrimitive.Close;

type PopoverContentProps = Omit<
  ComponentProps<typeof PopoverPrimitive.Content>,
  "aria-label" | "aria-labelledby" | "role"
> &
  (
    | {
        /** Names the panel for screen readers ("Choose start date"). Radix gives a popover role="dialog", and a dialog must have a name. */
        label: string;
        role?: never;
      }
    // For a pop-up that is not a dialog, such as the list under a combobox, which has its own role.
    | { label?: never; role: "presentation" }
  );

/** Floating panel: the elevated surface at 92% over a blur (plan 5.4), a soft scale-and-fade, and Esc to close. */
export function PopoverContent({
  className,
  sideOffset = 8,
  align = "start",
  label,
  role,
  ...props
}: PopoverContentProps) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        sideOffset={sideOffset}
        align={align}
        collisionPadding={12}
        {...(label ? { "aria-label": label } : { role })}
        className={cn(
          "material-sheet rounded-popover shadow-e2 text-body text-label z-50 max-w-[calc(100vw-1.5rem)] outline-none",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          // Grows from its trigger, on the spring (U6.1.9).
          "origin-(--radix-popover-content-transform-origin) ease-(--ease-spring)",
          "duration-[var(--duration-small)] motion-reduce:data-[state=open]:zoom-in-100 motion-reduce:data-[state=closed]:zoom-out-100",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}
