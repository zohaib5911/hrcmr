"use client";

import { useLayoutEffect, useRef, type ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { describedBy, FieldMessages, mergeRefs, useFieldIds } from "./field";

type TextAreaProps = Omit<ComponentProps<"textarea">, "placeholder"> & {
  label: string;
  hint?: string;
  error?: string | undefined;
  containerClassName?: string;
};

/** A multi-line field that grows with its text, up to a maximum height, then scrolls. */
export function TextArea({
  label,
  hint,
  error,
  containerClassName,
  className,
  id: idProp,
  ref,
  rows = 3,
  disabled,
  onInput,
  "aria-describedby": extraDescribedBy,
  ...props
}: TextAreaProps) {
  const ids = useFieldIds(idProp);
  const area = useRef<HTMLTextAreaElement>(null);

  function grow() {
    const node = area.current;
    if (!node) return;
    // Setting the height through the DOM, not a style attribute, which the CSP would block.
    node.style.height = "auto";
    node.style.height = `${node.scrollHeight}px`;
  }

  useLayoutEffect(grow, [props.value, props.defaultValue]);

  return (
    <div className={containerClassName}>
      <div
        className={cn(
          "bg-fill-secondary rounded-control relative px-3",
          "focus-within:outline-accent focus-within:outline-2 focus-within:outline-offset-2",
          error && "outline-danger outline-2 -outline-offset-2",
          disabled && "opacity-50",
        )}
      >
        <textarea
          {...props}
          ref={mergeRefs(area, ref)}
          id={ids.id}
          rows={rows}
          placeholder=" "
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(ids, { hint, error, extra: extraDescribedBy })}
          onInput={(event) => {
            grow();
            onInput?.(event);
          }}
          className={cn(
            "peer text-body text-label max-h-80 min-h-[3.25rem] w-full resize-none bg-transparent pt-6 pb-2 outline-none",
            className,
          )}
        />
        <label
          htmlFor={ids.id}
          className={cn(
            "text-placeholder pointer-events-none absolute left-3 motion-micro transition-all",
            "top-4 text-body",
            "peer-focus:top-2 peer-focus:text-caption",
            "peer-[:not(:placeholder-shown)]:top-2 peer-[:not(:placeholder-shown)]:text-caption",
          )}
        >
          {label}
        </label>
      </div>
      <FieldMessages ids={ids} hint={hint} error={error} />
    </div>
  );
}
