"use client";

import { Tooltip as TooltipPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Put once near the root. A short wait before the first tooltip, none between neighbours. */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300} skipDelayDuration={200}>
      {children}
    </TooltipPrimitive.Provider>
  );
}

interface TooltipProps {
  /** A short label. Not for essential information: touch screens and screen readers may not show it. */
  content: ReactNode;
  children: ReactNode;
  side?: ComponentProps<typeof TooltipPrimitive.Content>["side"];
}

/** A small dark label on hover and on keyboard focus. Wrap one focusable element. */
export function Tooltip({ content, children, side = "top" }: TooltipProps) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className={cn(
            "bg-label text-canvas rounded-control text-footnote z-[70] max-w-64 px-2.5 py-1.5 font-medium",
            "data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 duration-[var(--duration-micro)]",
          )}
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
