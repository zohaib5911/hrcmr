"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import {
  addDays,
  addMonths,
  compareIso,
  formatUkLong,
  isoWeekdayIndex,
  MONTH_NAMES,
  monthGrid,
  parseIso,
  startOfWeek,
  todayIso,
  WEEKDAY_NAMES,
} from "@/lib/ui/dates";
import type { Tone } from "@/lib/ui/status";
import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { Icon } from "./icon";

export interface DayMarker {
  /** Said by screen readers and shown as a tooltip: "Bank holiday". */
  label: string;
  tone: Tone;
}

interface CalendarMonthProps {
  /**
   * The day that holds keyboard focus. The month shown is this day's month, so moving focus past the
   * end of a month turns the page.
   */
  focused: string;
  onFocusedChange: (iso: string) => void;
  /** Called when a day is chosen with the mouse, Enter or Space. */
  onSelect: (iso: string) => void;
  selected?: string | null;
  /** Highlights a span of days (a date range or a leave request). */
  range?: { start: string | null; end: string | null };
  min?: string;
  max?: string;
  isDisabled?: (iso: string) => boolean;
  markers?: ReadonlyMap<string, DayMarker>;
  /** Move keyboard focus to the focused day when first shown (inside a popover). */
  autoFocus?: boolean;
  className?: string;
}

const subscribeNever = () => () => {};
const serverToday = () => null;

const DOT: Record<Tone, string> = {
  success: "bg-success-fill",
  warning: "bg-warning-fill",
  danger: "bg-danger-fill",
  info: "bg-info-fill",
  neutral: "bg-label-tertiary",
};

/** One month, six Monday-first weeks. Arrows, Home/End, PageUp/PageDown (with Shift for years). */
export function CalendarMonth({
  focused,
  onFocusedChange,
  onSelect,
  selected,
  range,
  min,
  max,
  isDisabled,
  markers,
  autoFocus = false,
  className,
}: CalendarMonthProps) {
  const headingId = useId();
  const grid = useRef<HTMLTableElement>(null);
  const keyboardMoved = useRef(autoFocus);
  const [hover, setHover] = useState<string | null>(null);
  // Today comes from the visitor's clock, so the server renders without it (no mismatch) and the
  // browser fills it in.
  const today = useSyncExternalStore(subscribeNever, todayIso, serverToday);

  const view = parseIso(focused) ?? { y: 1970, m: 1, d: 1 };
  const weeks = monthGrid(view.y, view.m);

  const disabled = (iso: string) =>
    (min !== undefined && compareIso(iso, min) < 0) ||
    (max !== undefined && compareIso(iso, max) > 0) ||
    isDisabled?.(iso) === true;

  // After a keyboard move, put focus on the new day's button.
  useEffect(() => {
    if (!keyboardMoved.current) return;
    grid.current?.querySelector<HTMLButtonElement>(`button[data-iso="${focused}"]`)?.focus();
  }, [focused]);

  function move(next: string) {
    keyboardMoved.current = true;
    onFocusedChange(next);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTableElement>) {
    const steps: Record<string, string> = {
      ArrowLeft: addDays(focused, -1),
      ArrowRight: addDays(focused, 1),
      ArrowUp: addDays(focused, -7),
      ArrowDown: addDays(focused, 7),
      Home: startOfWeek(focused),
      End: addDays(startOfWeek(focused), 6),
      PageUp: addMonths(focused, event.shiftKey ? -12 : -1),
      PageDown: addMonths(focused, event.shiftKey ? 12 : 1),
    };
    const next = steps[event.key];
    if (next === undefined) return;
    event.preventDefault();
    move(next);
  }

  const rangeStart = range?.start ?? null;
  const rangeEnd =
    range?.end ?? (rangeStart && hover && compareIso(hover, rangeStart) >= 0 ? hover : null);

  return (
    <div className={cn("w-full max-w-[19rem] select-none", className)}>
      <div className="mb-2 flex items-center justify-between">
        <IconButton label="Previous month" size="sm" onClick={() => move(addMonths(focused, -1))}>
          <Icon icon={ChevronLeft} size={20} />
        </IconButton>
        <h2 id={headingId} aria-live="polite" className="text-headline text-label">
          {MONTH_NAMES[view.m - 1]} {view.y}
        </h2>
        <IconButton label="Next month" size="sm" onClick={() => move(addMonths(focused, 1))}>
          <Icon icon={ChevronRight} size={20} />
        </IconButton>
      </div>
      <table
        ref={grid}
        role="grid"
        aria-labelledby={headingId}
        onKeyDown={onKeyDown}
        className="w-full table-fixed border-collapse"
      >
        <thead>
          <tr>
            {WEEKDAY_NAMES.map((name) => (
              <th
                key={name}
                scope="col"
                className="text-caption text-label-secondary pb-1 font-medium"
              >
                <abbr title={name} className="no-underline">
                  {name.slice(0, 2)}
                </abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody onMouseLeave={() => setHover(null)}>
          {weeks.map((week) => (
            <tr key={week[0]}>
              {week.map((iso) => {
                const day = parseIso(iso);
                const inMonth = day?.m === view.m;
                const isSelected = selected === iso;
                const isStart = rangeStart === iso;
                const isEnd = rangeEnd === iso;
                const inRange =
                  rangeStart !== null &&
                  rangeEnd !== null &&
                  compareIso(iso, rangeStart) > 0 &&
                  compareIso(iso, rangeEnd) < 0;
                const marker = markers?.get(iso);
                const isOff = disabled(iso);
                const isFocusStop = iso === focused;
                const label = [
                  formatUkLong(iso),
                  iso === today ? "today" : null,
                  isSelected || isStart || isEnd ? "selected" : null,
                  inRange ? "in the chosen range" : null,
                  marker?.label ?? null,
                  isOff ? "not available" : null,
                ]
                  .filter(Boolean)
                  .join(", ");
                const weekday = isoWeekdayIndex(iso);
                return (
                  <td
                    key={iso}
                    role="gridcell"
                    aria-selected={isSelected || isStart || isEnd || inRange}
                    className={cn(
                      "p-0 text-center",
                      inRange && "bg-accent-tint",
                      isStart && "bg-accent-tint rounded-l-full",
                      isEnd && "bg-accent-tint rounded-r-full",
                      weekday === 0 && inRange && "rounded-l-full",
                      weekday === 6 && inRange && "rounded-r-full",
                    )}
                  >
                    <button
                      type="button"
                      data-iso={iso}
                      tabIndex={isFocusStop ? 0 : -1}
                      aria-label={label}
                      aria-disabled={isOff || undefined}
                      onClick={() => {
                        if (isOff) return;
                        keyboardMoved.current = true;
                        onFocusedChange(iso);
                        onSelect(iso);
                      }}
                      onMouseEnter={() => setHover(iso)}
                      className={cn(
                        // Square cells that share the width: 44 px on touch and 36 px with a mouse, smaller only if the container is.
                        "text-body relative mx-auto grid aspect-square w-full max-w-11 place-items-center rounded-full tabular-nums transition-colors motion-micro pointer-fine:max-w-9",
                        inMonth ? "text-label" : "text-label-secondary",
                        !isSelected && !isStart && !isEnd && !isOff && "hover:bg-fill-secondary",
                        (isSelected || isStart || isEnd) &&
                          "bg-accent text-on-accent font-semibold",
                        iso === today &&
                          !(isSelected || isStart || isEnd) &&
                          "text-accent-text font-semibold",
                        isOff && "cursor-not-allowed opacity-40",
                      )}
                    >
                      {day?.d}
                      {marker ? (
                        <span
                          aria-hidden="true"
                          className={cn("absolute bottom-1 size-1 rounded-full", DOT[marker.tone])}
                        />
                      ) : null}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
