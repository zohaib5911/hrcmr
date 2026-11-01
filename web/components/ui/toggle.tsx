"use client";

import { Switch } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { useFieldIds } from "./field";

type ToggleProps = Omit<ComponentProps<typeof Switch.Root>, "children"> & {
  label: string;
  description?: string;
};

/** An on/off switch (plan 5.7: Toggle). The label is part of the control: click it or the switch. */
export function Toggle({ label, description, className, id: idProp, ...props }: ToggleProps) {
  const ids = useFieldIds(idProp);
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <label htmlFor={ids.id} className="flex min-w-0 flex-1 cursor-pointer flex-col">
        <span className="text-body text-label">{label}</span>
        {description ? (
          <span id={ids.hintId} className="text-subheadline text-label-secondary">
            {description}
          </span>
        ) : null}
      </label>
      <Switch.Root
        {...props}
        id={ids.id}
        aria-describedby={description ? ids.hintId : undefined}
        className={cn(
          "bg-label-tertiary data-[state=checked]:bg-accent rounded-pill relative h-[31px] w-[51px] shrink-0 cursor-pointer transition-colors motion-small",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        <Switch.Thumb className="shadow-e2 pointer-events-none block size-[27px] translate-x-0.5 rounded-full bg-knob transition-transform motion-small data-[state=checked]:translate-x-[22px] motion-reduce:transition-none" />
      </Switch.Root>
    </div>
  );
}
