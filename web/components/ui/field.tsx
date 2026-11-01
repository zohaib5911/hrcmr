"use client";

import { useId, type Ref } from "react";

import { cn } from "@/lib/utils";

/** Ids that tie a control to its hint and its error, so a screen reader reads them with the label. */
export function useFieldIds(idProp?: string) {
  const generated = useId();
  const id = idProp ?? generated;
  return { id, hintId: `${id}-hint`, errorId: `${id}-error` };
}

export function describedBy(
  ids: { hintId: string; errorId: string },
  parts: { hint?: string; error?: string | undefined; extra?: string | undefined },
): string | undefined {
  const list = [
    parts.error ? ids.errorId : null,
    parts.hint ? ids.hintId : null,
    parts.extra,
  ].filter(Boolean);
  return list.length > 0 ? list.join(" ") : undefined;
}

/** The hint under a control, and the error that replaces it (plan 5.7: inline validation). */
export function FieldMessages({
  ids,
  hint,
  error,
  className,
}: {
  ids: { hintId: string; errorId: string };
  hint?: string | undefined;
  error?: string | undefined;
  className?: string;
}) {
  return (
    <>
      {error ? (
        <p id={ids.errorId} className={cn("text-footnote text-danger mt-1.5 px-1", className)}>
          {error}
        </p>
      ) : null}
      {hint && !error ? (
        <p
          id={ids.hintId}
          className={cn("text-footnote text-label-secondary mt-1.5 px-1", className)}
        >
          {hint}
        </p>
      ) : null}
    </>
  );
}

/** Lets a component use its own ref and still hand one to its caller. */
export function mergeRefs<T>(...refs: (Ref<T> | undefined)[]) {
  return (node: T | null) => {
    for (const ref of refs) {
      if (typeof ref === "function") ref(node);
      else if (ref) (ref as { current: T | null }).current = node;
    }
  };
}

/** Sets a field's value the way typing would, so controlled and uncontrolled inputs both notice. */
export function setNativeValue(input: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype =
    input instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}
