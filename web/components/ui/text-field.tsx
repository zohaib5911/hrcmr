"use client";

import { X } from "lucide-react";
import { useRef, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { describedBy, FieldMessages, mergeRefs, setNativeValue, useFieldIds } from "./field";
import { Icon } from "./icon";

export type TextFieldProps = Omit<ComponentProps<"input">, "placeholder" | "size" | "prefix"> & {
  /** Rests inside the field and floats up when there is text or focus. It is the field's name. */
  label: string;
  hint?: string;
  /** Shown under the field. Setting it marks the field invalid. */
  error?: string | undefined;
  /** A clear (x) button once there is text. On by default. */
  clearable?: boolean;
  /** Inside the field, before the text (an icon or a currency sign). */
  startAdornment?: ReactNode;
  /** Inside the field, after the text and before the clear button. */
  endAdornment?: ReactNode;
  containerClassName?: string;
};

export function TextField({
  label,
  hint,
  error,
  clearable = true,
  startAdornment,
  endAdornment,
  containerClassName,
  className,
  id: idProp,
  ref,
  disabled,
  readOnly,
  "aria-describedby": extraDescribedBy,
  ...props
}: TextFieldProps) {
  const ids = useFieldIds(idProp);
  const input = useRef<HTMLInputElement>(null);
  const canClear = clearable && !disabled && !readOnly;

  function clear() {
    if (!input.current) return;
    setNativeValue(input.current, "");
    input.current.focus();
  }

  return (
    <div className={containerClassName}>
      <div
        className={cn(
          "group/field bg-fill-secondary rounded-control relative flex h-[3.25rem] items-center gap-2 px-3",
          "focus-within:outline-accent focus-within:outline-2 focus-within:outline-offset-2",
          error && "outline-danger outline-2 -outline-offset-2",
          disabled && "opacity-50",
        )}
      >
        {startAdornment ? (
          <span className="text-label flex shrink-0 items-center">{startAdornment}</span>
        ) : null}
        <div className="relative h-full min-w-0 flex-1">
          <input
            {...props}
            ref={mergeRefs(input, ref)}
            id={ids.id}
            placeholder=" "
            disabled={disabled}
            readOnly={readOnly}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy(ids, { hint, error, extra: extraDescribedBy })}
            className={cn(
              "peer text-body text-label h-full w-full min-w-0 bg-transparent pt-4 outline-none",
              "[&::-webkit-search-cancel-button]:hidden",
              className,
            )}
          />
          <label
            htmlFor={ids.id}
            className={cn(
              "text-placeholder pointer-events-none absolute top-1/2 left-0 -translate-y-1/2 truncate motion-micro transition-all",
              "text-body max-w-full",
              "peer-focus:top-2 peer-focus:translate-y-0 peer-focus:text-caption",
              "peer-[:not(:placeholder-shown)]:top-2 peer-[:not(:placeholder-shown)]:translate-y-0 peer-[:not(:placeholder-shown)]:text-caption",
            )}
          >
            {label}
          </label>
        </div>
        {endAdornment ? (
          <span className="text-label flex shrink-0 items-center">{endAdornment}</span>
        ) : null}
        {canClear ? (
          <IconButton
            label={`Clear ${label}`}
            size="sm"
            variant="gray"
            onClick={clear}
            tabIndex={-1}
            className="rounded-pill group-has-[input:placeholder-shown]/field:invisible"
          >
            <Icon icon={X} size={16} />
          </IconButton>
        ) : null}
      </div>
      <FieldMessages ids={ids} hint={hint} error={error} />
    </div>
  );
}
