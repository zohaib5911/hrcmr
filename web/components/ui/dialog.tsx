"use client";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { Icon } from "./icon";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

/** The dimmed backdrop's classes. Shared with Sheet and ConfirmDialog (which has its own Radix context). */
export const OVERLAY_CLASSES = cn(
  // The scrim blurs the page (U6.1.9) and appears at once: fading a full-screen blur would redraw
  // the blur on every frame of the fade. The sheet or dialog on top still fades and moves in.
  "bg-scrim scrim-blur fixed inset-0 z-50",
);

/**
 * The command palette's scrim: dimmed, not blurred (decision U6.1.9). The palette is opened often
 * and must open in one smooth step; a blurred page behind it is redrawn on every frame of its
 * zoom, which made the opening stutter on slow devices.
 */
export const PALETTE_SCRIM_CLASSES = "bg-scrim fixed inset-0 z-50";

export function Overlay({ className, ...props }: ComponentProps<typeof DialogPrimitive.Overlay>) {
  return <DialogPrimitive.Overlay className={cn(OVERLAY_CLASSES, className)} {...props} />;
}

/** The little bar at the top of a bottom sheet (phones only). */
export function Grabber() {
  return (
    <div
      aria-hidden="true"
      className="bg-label-tertiary/50 mx-auto mb-3 h-1 w-9 rounded-full md:hidden"
    />
  );
}

type DialogContentProps = Omit<ComponentProps<typeof DialogPrimitive.Content>, "title"> & {
  /** Names the dialog for screen readers. It is shown as the heading. */
  title: string;
  description?: string;
  /** Buttons along the bottom. Put the primary action last. */
  footer?: ReactNode;
  /** Hide the corner close button when the footer already has Cancel. */
  hideClose?: boolean;
};

/**
 * A focused task in the middle of the screen (a bottom sheet with a grabber below 768 px). It traps
 * focus, closes on Esc and gives focus back to what opened it.
 */
export function DialogContent({
  title,
  description,
  footer,
  hideClose = false,
  className,
  children,
  ...props
}: DialogContentProps) {
  return (
    <DialogPrimitive.Portal>
      <Overlay />
      <DialogPrimitive.Content
        className={cn(
          "material-modal text-label shadow-e3 fixed z-50 flex max-h-[calc(100dvh-2rem)] flex-col outline-none",
          // Phones: a sheet rising from the bottom edge.
          "max-md:inset-x-0 max-md:bottom-0 max-md:rounded-t-sheet max-md:px-5 max-md:pt-3 max-md:pb-[max(1.25rem,env(safe-area-inset-bottom))]",
          "max-md:data-[state=open]:slide-in-from-bottom max-md:data-[state=closed]:slide-out-to-bottom",
          // Larger screens: centred, scaling in from 0.96.
          "md:top-1/2 md:left-1/2 md:w-[min(32rem,calc(100vw-2rem))] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-sheet md:p-6",
          "md:data-[state=open]:zoom-in-96 md:data-[state=closed]:zoom-out-96",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
          "duration-[var(--duration-sheet)] ease-(--ease-spring) motion-reduce:data-[state=open]:zoom-in-100 motion-reduce:data-[state=closed]:zoom-out-100 motion-reduce:max-md:data-[state=open]:slide-in-from-bottom-0 motion-reduce:max-md:data-[state=closed]:slide-out-to-bottom-0",
          className,
        )}
        {...props}
      >
        <Grabber />
        <div className="flex items-start justify-between gap-4">
          <DialogPrimitive.Title className="text-title-3 text-label">{title}</DialogPrimitive.Title>
          {hideClose ? null : (
            <DialogPrimitive.Close asChild>
              <IconButton label="Close" size="sm" className="-mt-1 -mr-2">
                <Icon icon={X} size={20} />
              </IconButton>
            </DialogPrimitive.Close>
          )}
        </div>
        {description ? (
          <DialogPrimitive.Description className="text-callout text-label-secondary mt-1">
            {description}
          </DialogPrimitive.Description>
        ) : (
          <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        )}
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto">{children}</div>
        {footer ? <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div> : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
