"use client";

import { useState } from "react";

import { clamp, formatNumber, parseDecimal, stepValue } from "@/lib/ui/numbers";

import { TextField, type TextFieldProps } from "./text-field";

const UNITS = {
  currency: { prefix: "£", suffix: undefined, decimals: 2, step: 1 },
  hours: { prefix: undefined, suffix: "h", decimals: 1, step: 0.5 },
  plain: { prefix: undefined, suffix: undefined, decimals: 0, step: 1 },
} as const;

type NumberFieldProps = Omit<
  TextFieldProps,
  "value" | "defaultValue" | "onChange" | "type" | "startAdornment" | "endAdornment"
> & {
  /** The number, or null when the field is empty. */
  value: number | null;
  onChange: (value: number | null) => void;
  /** `currency` is pounds with two decimals; `hours` is one decimal with an "h". */
  unit?: keyof typeof UNITS;
  decimals?: number;
  step?: number;
  min?: number;
  max?: number;
};

/** Money and hours entry: type "£41,700", or use the arrow keys. It tidies the number when you leave. */
export function NumberField({
  value,
  onChange,
  unit = "plain",
  decimals: decimalsProp,
  step: stepProp,
  min,
  max,
  error,
  onBlur,
  onKeyDown,
  ...props
}: NumberFieldProps) {
  const preset = UNITS[unit];
  const decimals = decimalsProp ?? preset.decimals;
  const step = stepProp ?? preset.step;
  // What the person is typing, until they leave the field. `null` means "show the real value".
  const [draft, setDraft] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | undefined>();

  const shown = draft ?? (value === null ? "" : formatNumber(value, decimals));

  function change(text: string) {
    setDraft(text);
    setProblem(undefined);
    if (text.trim() === "") onChange(null);
    else {
      const parsed = parseDecimal(text);
      if (parsed !== null) onChange(parsed);
    }
  }

  function commit() {
    if (draft === null) return;
    if (draft.trim() === "") {
      setDraft(null);
      return;
    }
    const parsed = parseDecimal(draft);
    if (parsed === null) {
      setProblem("Enter a number, for example 1,250.50");
      return;
    }
    const next = clamp(parsed, min, max);
    onChange(next);
    setDraft(null);
  }

  return (
    <TextField
      {...props}
      type="text"
      inputMode="decimal"
      role="spinbutton"
      autoComplete="off"
      value={shown}
      error={error ?? problem}
      startAdornment={preset.prefix}
      endAdornment={preset.suffix}
      aria-valuenow={value ?? undefined}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuetext={
        value === null
          ? undefined
          : `${preset.prefix ?? ""}${formatNumber(value, decimals)}${preset.suffix ?? ""}`
      }
      onChange={(event) => change(event.target.value)}
      onBlur={(event) => {
        commit();
        onBlur?.(event);
      }}
      onKeyDown={(event) => {
        onKeyDown?.(event);
        if (event.defaultPrevented) return;
        if (event.key === "ArrowUp" || event.key === "ArrowDown") {
          event.preventDefault();
          const current = draft === null ? value : parseDecimal(draft);
          onChange(
            stepValue(current, step, event.key === "ArrowUp" ? 1 : -1, { decimals, min, max }),
          );
          setDraft(null);
          setProblem(undefined);
        } else if (event.key === "Enter") commit();
      }}
    />
  );
}
