/** Number entry for NumberField: UK formatting (41,700.50), strict parsing, drift-free stepping. */

// 1,234 / 1234 / 1,234.50 / .5, with an optional leading minus. A comma must group exactly three digits.
const DECIMAL = /^-?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?$/;

/** Reads what a person types: "£41,700", "7.5", "12h". Null if it is not a plain number. */
export function parseDecimal(text: string): number | null {
  const cleaned = text
    .replace(/\s+/g, "")
    .replace(/^(-?)£/, "$1")
    .replace(/(?:hours|hrs|hr|h)$/i, "");
  if (!/\d/.test(cleaned) || !DECIMAL.test(cleaned)) return null;
  return Number(cleaned.replace(/,/g, ""));
}

export function formatNumber(value: number, decimals: number): string {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function clamp(value: number, min?: number, max?: number): number {
  const lower = min === undefined ? value : Math.max(value, min);
  return max === undefined ? lower : Math.min(lower, max);
}

interface StepOptions {
  readonly decimals: number;
  readonly min?: number;
  readonly max?: number;
}

/** One step up (+1) or down (-1), rounded to the field's decimals so 0.1 + 0.2 is 0.3, then clamped. */
export function stepValue(
  value: number | null,
  step: number,
  direction: 1 | -1,
  { decimals, min, max }: StepOptions,
): number {
  const next = Number(((value ?? 0) + direction * step).toFixed(decimals));
  return clamp(next, min, max);
}
