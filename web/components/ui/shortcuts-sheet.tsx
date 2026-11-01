"use client";

import { Fragment } from "react";

import { keyLabel } from "@/lib/platform";
import { SHORTCUT_GROUPS } from "@/lib/shortcuts";

import { Sheet, SheetContent } from "./sheet";

interface ShortcutsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Cmd on Apple devices, Ctrl elsewhere. */
  apple: boolean;
}

function Keys({ keys, apple }: { keys: readonly string[]; apple: boolean }) {
  // "G" then "D" is two presses in a row; a modifier and a key are pressed together.
  const sequence = keys[0] === "G";
  return (
    <span className="flex items-center gap-1">
      {keys.map((key, index) => (
        <Fragment key={`${key}-${index}`}>
          {index > 0 && sequence ? (
            <span className="text-footnote text-label-secondary">then</span>
          ) : null}
          <kbd className="bg-fill-secondary text-callout text-label rounded-control min-w-7 px-2 py-0.5 text-center font-sans font-medium">
            {keyLabel(key, apple)}
          </kbd>
        </Fragment>
      ))}
    </span>
  );
}

/** An id for a group's heading: no spaces, so the section can name itself by it. */
const headingId = (title: string) => `shortcuts-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

/** Every keyboard shortcut in the app, listed (plan 8.19). Opened with "?". */
export function KeyboardShortcutsSheet({ open, onOpenChange, apple }: ShortcutsSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        title="Keyboard shortcuts"
        readOnly
        description="Shortcuts work anywhere except while you are typing in a field."
      >
        <div className="flex flex-col gap-6 pb-2">
          {SHORTCUT_GROUPS.map((group) => (
            <section key={group.title} aria-labelledby={headingId(group.title)}>
              <h3 id={headingId(group.title)} className="text-headline text-label mb-2">
                {group.title}
              </h3>
              <ul className="divide-separator divide-y">
                {group.shortcuts.map((shortcut) => (
                  <li
                    key={shortcut.keys.join("+")}
                    className="flex items-center justify-between gap-4 py-2"
                  >
                    <span className="min-w-0">
                      <span className="text-body text-label block">{shortcut.label}</span>
                      {shortcut.note ? (
                        <span className="text-footnote text-label-secondary block">
                          {shortcut.note}
                        </span>
                      ) : null}
                    </span>
                    <Keys keys={shortcut.keys} apple={apple} />
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
