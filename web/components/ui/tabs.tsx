"use client";

import { Tabs as TabsPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

/** Underline tabs for the sections of a record (Personal, Employment, Documents). */
export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("border-separator flex gap-6 overflow-x-auto border-b", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "text-callout text-label-secondary hover:text-label relative -mb-px shrink-0 cursor-pointer pb-3 pt-2 font-medium whitespace-nowrap transition-colors motion-micro",
        "data-[state=active]:text-label outline-none focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2 rounded-control",
        "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-transparent after:transition-colors",
        "data-[state=active]:after:bg-accent",
        className,
      )}
      {...props}
    />
  );
}
