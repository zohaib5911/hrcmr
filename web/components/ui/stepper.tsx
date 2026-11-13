import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

import { Icon } from "./icon";

export interface Step {
  id: string;
  label: string;
  description?: string;
}

interface StepperProps {
  steps: readonly Step[];
  /** Index of the step the person is on. Earlier steps are done. */
  current: number;
  /** "responsive" stacks the steps on phones and lays them in a row from md up, so long labels never overlap. */
  orientation?: "horizontal" | "vertical" | "responsive";
  className?: string;
}

/** Progress through a wizard or pipeline. Done, current and upcoming steps differ by icon and words, not colour alone. */
export function Stepper({ steps, current, orientation = "horizontal", className }: StepperProps) {
  return (
    <ol
      aria-label="Progress"
      className={cn(
        "flex gap-3",
        orientation === "horizontal" && "flex-row items-start",
        orientation === "vertical" && "flex-col",
        orientation === "responsive" && "flex-col md:flex-row md:items-start",
        className,
      )}
    >
      {steps.map((step, index) => {
        const state = index < current ? "done" : index === current ? "current" : "upcoming";
        return (
          <li
            key={step.id}
            aria-current={state === "current" ? "step" : undefined}
            className={cn(
              "flex min-w-0 gap-3",
              orientation === "horizontal" && "flex-1",
              orientation === "responsive" && "md:flex-1",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "text-footnote rounded-pill grid size-7 shrink-0 place-items-center font-semibold tabular-nums",
                state === "done" && "bg-accent text-on-accent",
                state === "current" && "bg-accent-tint text-accent-text ring-accent ring-2",
                state === "upcoming" && "bg-fill-secondary text-label",
              )}
            >
              {state === "done" ? <Icon icon={Check} size={16} /> : index + 1}
            </span>
            <span className="min-w-0">
              <span
                className={cn(
                  "text-callout block",
                  state === "current" ? "text-label font-semibold" : "text-label",
                )}
              >
                {step.label}
                <span className="sr-only">
                  {state === "done" ? " (completed)" : state === "current" ? " (current step)" : ""}
                </span>
              </span>
              {step.description ? (
                <span className="text-footnote text-label-secondary block">{step.description}</span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
