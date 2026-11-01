"use client";

import { LayoutGroup, motion, useReducedMotion } from "motion/react";
import { RadioGroup } from "radix-ui";
import { useId, type ReactNode } from "react";

import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface Segment<T extends string> {
  value: T;
  label: ReactNode;
  /** A plain-text name, when `label` is only an icon. */
  ariaLabel?: string;
}

interface SegmentedControlProps<T extends string> {
  /** What the choice is about ("View", "Range"). Names the group for screen readers. */
  label: string;
  value: T;
  onValueChange: (value: T) => void;
  segments: readonly Segment<T>[];
  size?: "sm" | "md";
  className?: string;
}

/**
 * Two to five views of the same thing (Calendar / Requests / Balances; Day / Week / Month). A radio
 * group: arrow keys move and choose, Tab leaves. The highlight glides with the spring, or just fades
 * with reduced motion.
 */
export function SegmentedControl<T extends string>({
  label,
  value,
  onValueChange,
  segments,
  size = "md",
  className,
}: SegmentedControlProps<T>) {
  const group = useId();
  const reduced = useReducedMotion();
  return (
    <LayoutGroup id={group}>
      <RadioGroup.Root
        aria-label={label}
        value={value}
        onValueChange={(next) => onValueChange(next as T)}
        orientation="horizontal"
        className={cn("bg-fill-secondary rounded-control inline-flex gap-0.5 p-0.5", className)}
      >
        {segments.map((segment) => {
          const selected = segment.value === value;
          return (
            <RadioGroup.Item
              key={segment.value}
              value={segment.value}
              aria-label={segment.ariaLabel}
              className={cn(
                "text-callout relative cursor-pointer rounded-[8px] px-3 font-medium whitespace-nowrap transition-colors motion-micro",
                "hit-target outline-none focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2",
                size === "sm" ? "h-7" : "h-8",
                "text-label",
              )}
            >
              {selected ? (
                <motion.span
                  layoutId="segment-thumb"
                  // With reduced motion the highlight jumps instead of gliding. The element is always
                  // there: the HTML must not depend on the preference, or the server's markup and the
                  // browser's would differ (a hydration mismatch).
                  transition={reduced ? { duration: 0 } : SPRING}
                  className="bg-elevated shadow-e1 absolute inset-0 rounded-[8px]"
                />
              ) : null}
              <span className="relative inline-flex items-center gap-1.5">{segment.label}</span>
            </RadioGroup.Item>
          );
        })}
      </RadioGroup.Root>
    </LayoutGroup>
  );
}
