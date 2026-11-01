"use client";

import { Check, Minus } from "lucide-react";
import { Checkbox as RadixCheckbox } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { useFieldIds } from "./field";
import { Icon } from "./icon";

type ControlProps = Omit<ComponentProps<typeof RadixCheckbox.Root>, "children">;

/** Just the box, for places that name it some other way (a table row's "Select Ada Lovelace"). */
export function CheckboxControl({ className, ...props }: ControlProps) {
  return (
    <RadixCheckbox.Root
      {...props}
      className={cn(
        "border-label-tertiary mt-0.5 grid size-5 shrink-0 cursor-pointer place-items-center rounded-[6px] border-[1.5px] transition-colors motion-micro",
        "data-[state=checked]:bg-accent data-[state=checked]:border-accent data-[state=indeterminate]:bg-accent data-[state=indeterminate]:border-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
    >
      <RadixCheckbox.Indicator className="text-on-accent">
        <Icon icon={props.checked === "indeterminate" ? Minus : Check} size={16} />
      </RadixCheckbox.Indicator>
    </RadixCheckbox.Root>
  );
}

type CheckboxProps = ControlProps & {
  label: string;
  description?: string;
};

/** A checkbox with its label. `checked="indeterminate"` shows a dash (some, not all). */
export function Checkbox({ label, description, className, id: idProp, ...props }: CheckboxProps) {
  const ids = useFieldIds(idProp);
  return (
    <div className={cn("flex items-start gap-3", className)}>
      <CheckboxControl
        {...props}
        id={ids.id}
        aria-describedby={description ? ids.hintId : undefined}
      />
      <label htmlFor={ids.id} className="flex min-w-0 cursor-pointer flex-col">
        <span className="text-body text-label">{label}</span>
        {description ? (
          <span id={ids.hintId} className="text-subheadline text-label-secondary">
            {description}
          </span>
        ) : null}
      </label>
    </div>
  );
}
