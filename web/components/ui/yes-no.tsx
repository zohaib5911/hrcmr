"use client";

import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: false, label: "No" },
  { value: true, label: "Yes" },
] as const;

interface YesNoProps {
  /** The question, which also names the group for screen readers. */
  label: string;
  /** `null` while it has not been answered. */
  value: boolean | null;
  onChange: (value: boolean) => void;
}

/** A yes or no question: two choices side by side, neither chosen until the person picks. */
export function YesNo({ label, value, onChange }: YesNoProps) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-callout text-label">{label}</p>
      <div
        role="radiogroup"
        aria-label={label}
        className="bg-fill-secondary rounded-control inline-flex w-fit gap-0.5 p-0.5"
      >
        {OPTIONS.map((option) => {
          const selected = value === option.value;
          return (
            <button
              key={option.label}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(option.value)}
              className={cn(
                "text-callout hit-target cursor-pointer rounded-[8px] px-4 font-medium outline-none",
                "focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2",
                selected ? "bg-elevated text-label shadow-e1 font-semibold" : "text-label",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
