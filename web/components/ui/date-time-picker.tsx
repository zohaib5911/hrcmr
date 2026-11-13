"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

import { DatePicker } from "./date-picker";
import { FieldMessages, useFieldIds } from "./field";
import { TimePicker } from "./time-picker";

interface Parts {
  date: string | null;
  time: string | null;
}

function split(value: string | null): Parts {
  if (!value) return { date: null, time: null };
  const [date = null, time = null] = value.split("T");
  return { date, time: time ? time.slice(0, 5) : null };
}

function join({ date, time }: Parts): string | null {
  return date && time ? `${date}T${time}` : null;
}

interface DateTimePickerProps {
  /** Names the pair of fields, for screen readers: "Interview date and time". */
  legend: string;
  /** A local date and time, "2026-11-01T09:30" (the wire format of a datetime-local field), or null. */
  value: string | null;
  onChange: (value: string | null) => void;
  dateLabel?: string;
  timeLabel?: string;
  required?: boolean;
  min?: string;
  max?: string;
  error?: string | undefined;
  hint?: string;
  className?: string;
}

/**
 * A date and a 24-hour time side by side, shown the UK way (1 Nov 2026, 09:30) in place of the
 * browser's own datetime field. The value is set once both halves are filled in.
 */
export function DateTimePicker({
  legend,
  value,
  onChange,
  dateLabel = "Date",
  timeLabel = "Time",
  required,
  min,
  max,
  error,
  hint,
  className,
}: DateTimePickerProps) {
  const ids = useFieldIds();
  const [parts, setParts] = useState<Parts>(() => split(value));
  // Follow a value set from outside (a reset, or a record loaded later), but keep a half-filled pair.
  if (value !== join(parts) && (value !== null || (parts.date && parts.time))) {
    setParts(split(value));
  }

  function update(next: Parts) {
    setParts(next);
    onChange(join(next));
  }

  return (
    <fieldset className={cn("min-w-0", className)}>
      <legend className="sr-only">{legend}</legend>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <DatePicker
          label={dateLabel}
          required={required}
          value={parts.date}
          min={min}
          max={max}
          onChange={(date) => update({ ...parts, date })}
        />
        <TimePicker
          label={timeLabel}
          required={required}
          value={parts.time}
          onChange={(time) => update({ ...parts, time })}
        />
      </div>
      <FieldMessages ids={ids} hint={hint} error={error} />
    </fieldset>
  );
}
