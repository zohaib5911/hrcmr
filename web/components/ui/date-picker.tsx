"use client";

import { Calendar } from "lucide-react";
import { useRef, useState } from "react";

import { compareIso, formatUk, parseUk, todayIso } from "@/lib/ui/dates";
import { cn } from "@/lib/utils";

import { IconButton } from "./button";
import { CalendarMonth, type DayMarker } from "./calendar-month";
import { FieldMessages, useFieldIds } from "./field";
import { Icon } from "./icon";
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from "./popover";
import { TextField, type TextFieldProps } from "./text-field";

type BaseProps = Omit<
  TextFieldProps,
  | "value"
  | "defaultValue"
  | "onChange"
  | "type"
  | "startAdornment"
  | "endAdornment"
  | "clearable"
  | "ref"
>;

interface Constraints {
  min?: string;
  max?: string;
  isDateDisabled?: (iso: string) => boolean;
  markers?: ReadonlyMap<string, DayMarker>;
}

/** Why a date cannot be chosen, in words, or undefined if it can. */
function whyNot(iso: string, { min, max, isDateDisabled }: Constraints): string | undefined {
  if (
    min !== undefined &&
    max !== undefined &&
    (compareIso(iso, min) < 0 || compareIso(iso, max) > 0)
  ) {
    return `Choose a date from ${formatUk(min)} to ${formatUk(max)}`;
  }
  if (min !== undefined && compareIso(iso, min) < 0)
    return `Choose a date on or after ${formatUk(min)}`;
  if (max !== undefined && compareIso(iso, max) > 0)
    return `Choose a date on or before ${formatUk(max)}`;
  if (isDateDisabled?.(iso)) return "That date is not available";
  return undefined;
}

/**
 * Typed entry for one date: the text the person is typing is a draft until they leave the field or
 * press Enter, when it is read as a UK date and checked.
 */
function useDateText(
  value: string | null,
  onChange: (iso: string | null) => void,
  constraints: Constraints,
) {
  const [draft, setDraft] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | undefined>();

  return {
    shown: draft ?? (value ? formatUk(value) : ""),
    problem,
    type(text: string) {
      setDraft(text);
      setProblem(undefined);
    },
    commit() {
      if (draft === null) return;
      const text = draft.trim();
      if (!text) {
        onChange(null);
        setDraft(null);
        return;
      }
      const iso = parseUk(text);
      const reason = iso ? whyNot(iso, constraints) : "Enter a date like 1 Nov 2026";
      if (!iso || reason) {
        setProblem(reason);
        return;
      }
      onChange(iso);
      setDraft(null);
    },
    reset() {
      setDraft(null);
      setProblem(undefined);
    },
  };
}

function startingFocus(value: string | null, { min, max }: Constraints): string {
  const day = value ?? todayIso();
  if (min !== undefined && compareIso(day, min) < 0) return min;
  if (max !== undefined && compareIso(day, max) > 0) return max;
  return day;
}

type DatePickerProps = BaseProps &
  Constraints & {
    /** An ISO date ("2026-11-01"), or null when empty. */
    value: string | null;
    onChange: (value: string | null) => void;
  };

/** One date: type it ("1 Nov 2026", "1/11/26") or choose it from the calendar. Dates are shown as 1 Nov 2026. */
export function DatePicker({
  value,
  onChange,
  min,
  max,
  isDateDisabled,
  markers,
  error,
  onBlur,
  onKeyDown,
  ...props
}: DatePickerProps) {
  const constraints = { min, max, isDateDisabled, markers };
  const text = useDateText(value, onChange, constraints);
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        if (next) setFocused(startingFocus(value, constraints));
        setOpen(next);
      }}
    >
      <PopoverAnchor asChild>
        <div>
          <TextField
            {...props}
            ref={input}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            clearable
            value={text.shown}
            error={error ?? text.problem}
            endAdornment={
              <PopoverTrigger asChild>
                <IconButton
                  label={`Choose ${props.label.toLowerCase()} from a calendar`}
                  size="sm"
                  className="-mr-1"
                >
                  <Icon icon={Calendar} size={20} />
                </IconButton>
              </PopoverTrigger>
            }
            onChange={(event) => text.type(event.target.value)}
            onBlur={(event) => {
              text.commit();
              onBlur?.(event);
            }}
            onKeyDown={(event) => {
              onKeyDown?.(event);
              if (event.defaultPrevented) return;
              if (event.key === "Enter") text.commit();
              if (event.key === "ArrowDown" && event.altKey) {
                event.preventDefault();
                setFocused(startingFocus(value, constraints));
                setOpen(true);
              }
            }}
          />
        </div>
      </PopoverAnchor>
      <PopoverContent
        label={`Choose ${props.label.toLowerCase()}`}
        className="p-3"
        onOpenAutoFocus={(event) => event.preventDefault()}
        // Back to the text box, where the person was typing, not to the calendar icon.
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          input.current?.focus();
        }}
      >
        <CalendarMonth
          autoFocus
          focused={focused ?? startingFocus(value, constraints)}
          onFocusedChange={setFocused}
          selected={value}
          min={min}
          max={max}
          isDisabled={isDateDisabled}
          markers={markers}
          onSelect={(iso) => {
            onChange(iso);
            text.reset();
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

export interface DateRange {
  start: string | null;
  end: string | null;
}

type DateRangePickerProps = Constraints & {
  /** Names the pair of fields, for screen readers: "Leave dates". */
  legend: string;
  value: DateRange;
  onChange: (value: DateRange) => void;
  startLabel?: string;
  endLabel?: string;
  error?: string | undefined;
  hint?: string;
  className?: string;
};

/** A start and an end date. Click two days on the calendar, or type them. The end cannot be before the start. */
export function DateRangePicker({
  legend,
  value,
  onChange,
  startLabel = "Start date",
  endLabel = "End date",
  min,
  max,
  isDateDisabled,
  markers,
  error,
  hint,
  className,
}: DateRangePickerProps) {
  const ids = useFieldIds();
  const constraints = { min, max, isDateDisabled, markers };
  const startText = useDateText(
    value.start,
    (start) => onChange({ start, end: value.end }),
    constraints,
  );
  const endText = useDateText(value.end, (end) => onChange({ start: value.start, end }), {
    ...constraints,
    min: value.start && (min === undefined || compareIso(value.start, min) > 0) ? value.start : min,
  });
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const endInput = useRef<HTMLInputElement>(null);

  function pick(iso: string) {
    if (value.start === null || value.end !== null) {
      onChange({ start: iso, end: null });
      startText.reset();
      endText.reset();
    } else {
      onChange(
        compareIso(iso, value.start) < 0
          ? { start: iso, end: value.start }
          : { start: value.start, end: iso },
      );
      endText.reset();
      setOpen(false);
    }
  }

  return (
    <fieldset className={cn("min-w-0", className)}>
      <legend className="sr-only">{legend}</legend>
      <Popover
        open={open}
        onOpenChange={(next) => {
          if (next) setFocused(startingFocus(value.start, constraints));
          setOpen(next);
        }}
      >
        <PopoverAnchor asChild>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField
              label={startLabel}
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={startText.shown}
              error={startText.problem}
              onChange={(event) => startText.type(event.target.value)}
              onBlur={startText.commit}
              onKeyDown={(event) => event.key === "Enter" && startText.commit()}
            />
            <TextField
              ref={endInput}
              label={endLabel}
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={endText.shown}
              error={endText.problem}
              endAdornment={
                <PopoverTrigger asChild>
                  <IconButton
                    label={`Choose ${legend.toLowerCase()} from a calendar`}
                    size="sm"
                    className="-mr-1"
                  >
                    <Icon icon={Calendar} size={20} />
                  </IconButton>
                </PopoverTrigger>
              }
              onChange={(event) => endText.type(event.target.value)}
              onBlur={endText.commit}
              onKeyDown={(event) => event.key === "Enter" && endText.commit()}
            />
          </div>
        </PopoverAnchor>
        <PopoverContent
          label={`Choose ${legend.toLowerCase()}`}
          className="p-3"
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            endInput.current?.focus();
          }}
        >
          <CalendarMonth
            autoFocus
            focused={focused ?? startingFocus(value.start, constraints)}
            onFocusedChange={setFocused}
            range={value}
            min={min}
            max={max}
            isDisabled={isDateDisabled}
            markers={markers}
            onSelect={pick}
          />
          <p className="text-footnote text-label-secondary mt-2 px-1">
            {value.start && !value.end
              ? "Now choose the last day."
              : "Choose the first day, then the last day."}
          </p>
        </PopoverContent>
      </Popover>
      <FieldMessages ids={ids} hint={hint} error={error} />
    </fieldset>
  );
}
