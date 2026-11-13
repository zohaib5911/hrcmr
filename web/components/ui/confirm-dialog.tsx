"use client";

import { AlertDialog } from "radix-ui";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Button } from "./button";
import { OVERLAY_CLASSES } from "./dialog";
import { TextField } from "./text-field";

interface ConfirmDialogProps {
  /** The button (or menu item) that opens it. Rendered as-is. */
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  /** Red button, for anything that cannot be undone. */
  destructive?: boolean;
  /** For deletions: the name of the record. The person must type it before the button works. */
  requireText?: string;
  children?: ReactNode;
  confirmDisabled?: boolean;
  onConfirm: () => void | Promise<void>;
}

/**
 * "Are you sure?" for actions that matter (plan 5.7). Focus starts on Cancel, so pressing Enter by
 * reflex does nothing harmful. A deletion asks for the record's name to be typed.
 */
export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive = false,
  requireText,
  onConfirm,
  children,
  confirmDisabled = false,
}: ConfirmDialogProps) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const allowed = !confirmDisabled && (requireText === undefined || typed.trim() === requireText);

  async function confirm() {
    if (!allowed || busy) return;
    setBusy(true);
    try {
      await onConfirm();
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AlertDialog.Root
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        setOpen(next);
        if (!next) setTyped("");
      }}
    >
      <AlertDialog.Trigger asChild>{trigger}</AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className={OVERLAY_CLASSES} />
        <AlertDialog.Content
          className={cn(
            "material-sheet text-label shadow-e3 rounded-sheet fixed top-1/2 left-1/2 z-50 w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 p-6 outline-none",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-96",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-96",
            "duration-[var(--duration-sheet)] motion-reduce:data-[state=open]:zoom-in-100 motion-reduce:data-[state=closed]:zoom-out-100",
          )}
        >
          <AlertDialog.Title className="text-title-3 text-label">{title}</AlertDialog.Title>
          <AlertDialog.Description className="text-callout text-label-secondary mt-1">
            {description}
          </AlertDialog.Description>
          {children ? <div className="mt-4 grid gap-4">{children}</div> : null}
          {requireText !== undefined ? (
            <div className="mt-4">
              <TextField
                label={`Type ${requireText} to confirm`}
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                autoComplete="off"
                spellCheck={false}
                clearable={false}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void confirm();
                  }
                }}
              />
            </div>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <Button variant="gray" disabled={busy}>
                {cancelLabel}
              </Button>
            </AlertDialog.Cancel>
            <Button
              variant={destructive ? "destructive" : "filled"}
              loading={busy}
              disabled={!allowed}
              onClick={() => void confirm()}
            >
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
