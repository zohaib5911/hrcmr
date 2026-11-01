"use client";

import { Clock } from "lucide-react";
import { useId, useState } from "react";

import { parseTime, stepTime } from "@/lib/ui/time";

import { Icon } from "./icon";
import { TextField, type TextFieldProps } from "./text-field";

type TimePickerProps = Omit<
  TextFieldProps,
  "value" | "defaultValue" | "onChange" | "type" | "startAdornment" | "endAdornment"
> & {
  /** "HH:MM" in 24-hour time, or null when empty. */
  value: string | null;
  onChange: (value: string | null) => void;
  /** Minutes moved by the up and down arrow keys. */
  step?: number;
};

/** 24-hour time (plan 5.8). Type "9", "930", "9.30" or "5pm", or use the arrow keys. */
export function TimePicker({
  value,
  onChange,
  step = 15,
  error,
  onBlur,
  onKeyDown,
  ...props
}: TimePickerProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | undefined>();
  const helpId = useId();

  function commit() {
    if (draft === null) return;
    if (draft.trim() === "") {
      onChange(null);
      setDraft(null);
      return;
    }
    const parsed = parseTime(draft);
    if (parsed === null) {
      setProblem("Enter a time like 09:30");
      return;
    }
    onChange(parsed);
    setDraft(null);
  }

  return (
    <>
      <TextField
        {...props}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        value={draft ?? value ?? ""}
        error={error ?? problem}
        startAdornment={<Icon icon={Clock} size={16} />}
        aria-describedby={[helpId, props["aria-describedby"]].filter(Boolean).join(" ")}
        onChange={(event) => {
          setDraft(event.target.value);
          setProblem(undefined);
        }}
        onBlur={(event) => {
          commit();
          onBlur?.(event);
        }}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (event.defaultPrevented) return;
          if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault();
            const current = draft === null ? value : parseTime(draft);
            onChange(stepTime(current, step, event.key === "ArrowUp" ? 1 : -1));
            setDraft(null);
            setProblem(undefined);
          } else if (event.key === "Enter") commit();
        }}
      />
      <span id={helpId} className="sr-only">
        Use the up and down arrow keys to change the time.
      </span>
    </>
  );
}
