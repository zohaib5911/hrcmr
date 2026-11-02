"use client";

import type { FormEvent, ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import type { Problem } from "@/lib/auth/request";

interface FormSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  /** Called with the form's submit; the sheet's own Save button submits it. */
  onSubmit: (event: FormEvent) => void;
  busy?: boolean;
  /** A problem that is not about one field. */
  problem?: Problem | null;
  /** Offered when editing something that can be put away (archived), separated from Save. */
  archive?: { label: string; question: string; detail: string; onConfirm: () => Promise<void> };
  children: ReactNode;
}

/** The sheet every set-up form uses: fields, then Cancel and Save, with Archive kept apart and confirmed. */
export function FormSheet({
  open,
  onOpenChange,
  title,
  description,
  onSubmit,
  busy = false,
  problem,
  archive,
  children,
}: FormSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        title={title}
        {...(description ? { description } : {})}
        footer={
          <div className="flex w-full flex-wrap items-center justify-between gap-2">
            {archive ? (
              <ConfirmDialog
                trigger={<Button variant="plain">{archive.label}</Button>}
                title={archive.question}
                description={archive.detail}
                confirmLabel={archive.label}
                destructive
                onConfirm={archive.onConfirm}
              />
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button variant="gray" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" form="set-up-form" loading={busy}>
                Save
              </Button>
            </div>
          </div>
        }
      >
        <form id="set-up-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4 pb-2">
          {problem ? <Alert tone="danger" title={problem.message} /> : null}
          {children}
        </form>
      </SheetContent>
    </Sheet>
  );
}
