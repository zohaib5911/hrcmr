"use client";

import { useRef, useState } from "react";

import { Button, type buttonVariants } from "./button";
import type { VariantProps } from "class-variance-authority";

interface InlineConfirmProps {
  /** The button that starts it, such as "Archive". */
  label: string;
  /** The question that replaces the button, such as "Archive this employee?". */
  prompt: string;
  confirmLabel?: string;
  destructive?: boolean;
  variant?: VariantProps<typeof buttonVariants>["variant"];
  disabled?: boolean;
  onConfirm: () => void | Promise<void>;
}

/**
 * A lighter confirmation than a dialog (plan 5.7: InlineConfirm): the button turns into a question
 * with Confirm and Cancel right where it was. Esc cancels. Focus lands on Cancel for risky actions.
 */
export function InlineConfirm({
  label,
  prompt,
  confirmLabel = "Confirm",
  destructive = false,
  variant = "gray",
  disabled,
  onConfirm,
}: InlineConfirmProps) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);

  function stop() {
    setAsking(false);
    // Put focus back where the person was; the button is a new element after the question closes.
    requestAnimationFrame(() => trigger.current?.focus());
  }

  async function confirm() {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
      stop();
    }
  }

  if (!asking) {
    return (
      <Button
        ref={trigger}
        variant={variant}
        size="sm"
        disabled={disabled}
        onClick={() => setAsking(true)}
      >
        {label}
      </Button>
    );
  }

  return (
    <div
      role="group"
      aria-label={prompt}
      className="flex flex-wrap items-center gap-2"
      onKeyDown={(event) => {
        if (event.key === "Escape" && !busy) {
          event.stopPropagation();
          stop();
        }
      }}
    >
      <span className="text-callout text-label">{prompt}</span>
      <Button
        size="sm"
        variant={destructive ? "destructive" : "filled"}
        loading={busy}
        autoFocus={!destructive}
        onClick={() => void confirm()}
      >
        {confirmLabel}
      </Button>
      <Button size="sm" variant="plain" autoFocus={destructive} disabled={busy} onClick={stop}>
        Cancel
      </Button>
    </div>
  );
}
