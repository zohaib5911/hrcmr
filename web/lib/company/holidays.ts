import type { components } from "@/lib/api/client";

type Colour = components["schemas"]["HolidayTypeOut"]["colour"];

/** The colours a holiday type can have, as the design's own tokens. */
export const COLOURS: readonly { value: Colour; label: string }[] = [
  { value: "blue", label: "Blue" },
  { value: "green", label: "Green" },
  { value: "orange", label: "Orange" },
  { value: "red", label: "Red" },
  { value: "gray", label: "Gray" },
];

export const COLOUR_CLASS: Record<Colour, string> = {
  blue: "bg-info-fill",
  green: "bg-success-fill",
  orange: "bg-warning-fill",
  red: "bg-danger-fill",
  gray: "bg-label-tertiary",
};

const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
const MONTH = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

const at = (iso: string) => new Date(`${iso}T00:00:00Z`);
const short = (date: Date) => `${date.getUTCDate()} ${MONTH[date.getUTCMonth()]}`;

/** "1 Jan 2026". */
export function shortDate(iso: string): string {
  const date = at(iso);
  return `${short(date)} ${date.getUTCFullYear()}`;
}

/** "Thu 1 Jan 2026". Written out here, so it reads the same in every browser. */
export function longDate(iso: string): string {
  const date = at(iso);
  return `${WEEKDAY[date.getUTCDay()]} ${short(date)} ${date.getUTCFullYear()}`;
}

/** "3 Aug to 14 Aug 2026", "24 Dec 2026 to 2 Jan 2027", or "1 May 2026" for a single day. */
export function dayRange(start: string, end: string): string {
  const from = at(start);
  const to = at(end);
  if (start === end) return `${short(from)} ${from.getUTCFullYear()}`;
  const sameYear = from.getUTCFullYear() === to.getUTCFullYear();
  return `${short(from)}${sameYear ? "" : ` ${from.getUTCFullYear()}`} to ${short(to)} ${to.getUTCFullYear()}`;
}
