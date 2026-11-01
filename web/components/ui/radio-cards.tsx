"use client";

import { RadioGroup } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export interface RadioCardOption {
  value: string;
  title: string;
  description?: string;
  disabled?: boolean;
}

type RadioCardsProps = Omit<ComponentProps<typeof RadioGroup.Root>, "children"> & {
  /** The question the cards answer: it names the group for screen readers. */
  legend: string;
  options: readonly RadioCardOption[];
  columns?: 1 | 2 | 3;
};

const COLUMNS = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-3",
} as const;

/** Choose one of a few options, each with a title and a sentence (roles, check types, confirmation modes). */
export function RadioCards({ legend, options, columns = 1, className, ...props }: RadioCardsProps) {
  return (
    <RadioGroup.Root
      aria-label={legend}
      className={cn("grid gap-3", COLUMNS[columns], className)}
      {...props}
    >
      {options.map((option) => (
        <RadioGroup.Item
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className={cn(
            "bg-elevated rounded-card shadow-e1 flex cursor-pointer items-start gap-3 p-4 text-left transition-colors motion-micro",
            "data-[state=checked]:ring-accent data-[state=checked]:ring-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          <span
            aria-hidden="true"
            className="border-label-tertiary mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border-[1.5px] [[data-state=checked]_&]:border-accent"
          >
            <RadioGroup.Indicator className="bg-accent size-2.5 rounded-full" />
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="text-headline text-label">{option.title}</span>
            {option.description ? (
              <span className="text-callout text-label-secondary">{option.description}</span>
            ) : null}
          </span>
        </RadioGroup.Item>
      ))}
    </RadioGroup.Root>
  );
}
