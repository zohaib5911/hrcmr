import { WEEKDAYS } from "./working-pattern";

export type Frequency = "weekly" | "fortnightly" | "four_weekly" | "monthly";
export type PayDayKind = "weekday" | "day_of_month" | "last_day" | "last_working_day";

export const FREQUENCIES: readonly { value: Frequency; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "fortnightly", label: "Every two weeks" },
  { value: "four_weekly", label: "Every four weeks" },
  { value: "monthly", label: "Monthly" },
];

export const CURRENCIES = ["GBP", "EUR", "USD"] as const;

/** "£28,000", or "€28,000" for a euro band; the API sends the amount as text. */
export function formatMoney(amount: string | number, currency = "GBP", decimals = 0): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(amount));
}

/** "£28,000 to £34,000 a year". */
export function bandRange(min: string | number, max: string | number, currency: string): string {
  return `${formatMoney(min, currency)} to ${formatMoney(max, currency)} a year`;
}

function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

/** "Weekly, on Fridays", "Monthly, on the 25th", "Monthly, on the last working day". */
export function scheduleSummary(
  frequency: Frequency,
  kind: PayDayKind,
  value: number | null | undefined,
): string {
  const label = FREQUENCIES.find((f) => f.value === frequency)?.label ?? frequency;
  if (kind === "weekday") return `${label}, on ${WEEKDAYS[(value ?? 1) - 1] ?? "a weekday"}s`;
  if (kind === "day_of_month") return `${label}, on the ${ordinal(value ?? 1)}`;
  if (kind === "last_day") return `${label}, on the last day of the month`;
  return `${label}, on the last working day`;
}

/** "20%", "19.5%". */
export function percent(value: string | number): string {
  return `${Number(value)}%`;
}
