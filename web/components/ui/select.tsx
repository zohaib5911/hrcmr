import { ChevronDown } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { describedBy, FieldMessages, useFieldIds } from "./field";
import { Icon } from "./icon";

type SelectProps = Omit<ComponentProps<"select">, "size"> & {
  label: string;
  hint?: string;
  error?: string | undefined;
  /** Shown while nothing is chosen. Leave out when there is always a choice. */
  placeholder?: string;
  containerClassName?: string;
};

/**
 * The browser's own select, styled. On a phone that is the system picker, which is what people expect
 * (plan 5.7: native on mobile), and it is fully accessible on every platform. Pass <option>s as children.
 */
export function Select({
  label,
  hint,
  error,
  placeholder,
  containerClassName,
  className,
  children,
  id: idProp,
  disabled,
  "aria-describedby": extraDescribedBy,
  ...props
}: SelectProps) {
  const ids = useFieldIds(idProp);
  return (
    <div className={containerClassName}>
      <div
        className={cn(
          "bg-fill-secondary rounded-control relative h-[3.25rem]",
          "focus-within:outline-accent focus-within:outline-2 focus-within:outline-offset-2",
          error && "outline-danger outline-2 -outline-offset-2",
          disabled && "opacity-50",
        )}
      >
        <label
          htmlFor={ids.id}
          className="text-caption text-placeholder pointer-events-none absolute top-2 left-3"
        >
          {label}
        </label>
        <select
          {...props}
          id={ids.id}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(ids, { hint, error, extra: extraDescribedBy })}
          className={cn(
            "text-body text-label h-full w-full cursor-pointer appearance-none bg-transparent pt-4 pr-9 pl-3 outline-none",
            className,
          )}
        >
          {placeholder ? (
            <option value="" disabled hidden>
              {placeholder}
            </option>
          ) : null}
          {children}
        </select>
        <Icon
          icon={ChevronDown}
          size={16}
          className="text-label-secondary pointer-events-none absolute top-1/2 right-3 -translate-y-1/2"
        />
      </div>
      <FieldMessages ids={ids} hint={hint} error={error} />
    </div>
  );
}
