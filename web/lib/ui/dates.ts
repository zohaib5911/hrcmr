/**
 * Calendar-date logic for the date pickers. A date is an ISO string, "2026-11-01", never a `Date`:
 * a `Date` carries a time and a time zone, and "the day of birth" or "the start date" has neither.
 * All arithmetic is done on UTC calendar days, so the clocks changing (23 and 25 hour days) can never
 * move a date. Weeks start on Monday, as in the UK.
 */

export interface Ymd {
  readonly y: number;
  /** 1 to 12. */
  readonly m: number;
  readonly d: number;
}

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

export const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

const MONTH_SHORT = MONTH_NAMES.map((name) => name.slice(0, 3));
export const WEEKDAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

export function daysInMonth(y: number, m: number): number {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

/** Reads a strict `YYYY-MM-DD`; null unless it is a real calendar date. */
export function parseIso(iso: string): Ymd | null {
  const match = ISO.exec(iso);
  if (!match) return null;
  return validYmd(Number(match[1]), Number(match[2]), Number(match[3]));
}

function validYmd(y: number, m: number, d: number): Ymd | null {
  if (y < 1 || m < 1 || m > 12 || d < 1 || d > daysInMonth(y, m)) return null;
  return { y, m, d };
}

export function toIso({ y, m, d }: Ymd): string {
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function utc(iso: string): Date {
  const ymd = parseIso(iso);
  if (!ymd) throw new Error(`Not a date: ${iso}`);
  return new Date(Date.UTC(ymd.y, ymd.m - 1, ymd.d));
}

function fromUtc(date: Date): string {
  return toIso({ y: date.getUTCFullYear(), m: date.getUTCMonth() + 1, d: date.getUTCDate() });
}

export function addDays(iso: string, days: number): string {
  const date = utc(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return fromUtc(date);
}

/** Moves by whole months, keeping the day where possible: 31 Jan + 1 month is 28 or 29 Feb. */
export function addMonths(iso: string, months: number): string {
  const { y, m, d } = parseIso(iso) ?? { y: 0, m: 0, d: 0 };
  const index = y * 12 + (m - 1) + months;
  const year = Math.floor(index / 12);
  const month = (index % 12) + 1;
  return toIso({ y: year, m: month, d: Math.min(d, daysInMonth(year, month)) });
}

/** Monday is 0, Sunday is 6. */
export function isoWeekdayIndex(iso: string): number {
  return (utc(iso).getUTCDay() + 6) % 7;
}

export function startOfWeek(iso: string): string {
  return addDays(iso, -isoWeekdayIndex(iso));
}

export function compareIso(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Six weeks of seven days that contain the month, Monday first. Always six rows, so the height is steady. */
export function monthGrid(year: number, month: number): string[][] {
  const first = startOfWeek(toIso({ y: year, m: month, d: 1 }));
  return Array.from({ length: 6 }, (_, week) =>
    Array.from({ length: 7 }, (_, day) => addDays(first, week * 7 + day)),
  );
}

/** "1 Nov 2026" (plan 5.8). */
export function formatUk(iso: string): string {
  const { y, m, d } = parseIso(iso) ?? { y: 0, m: 1, d: 0 };
  return `${d} ${MONTH_SHORT[m - 1]} ${y}`;
}

/** "Sunday 1 November 2026", for screen readers and calendar cells. */
export function formatUkLong(iso: string): string {
  const { y, m, d } = parseIso(iso) ?? { y: 0, m: 1, d: 0 };
  return `${WEEKDAY_NAMES[isoWeekdayIndex(iso)]} ${d} ${MONTH_NAMES[m - 1]} ${y}`;
}

function monthFromWord(word: string): number | null {
  const lower = word.toLowerCase();
  if (lower === "sept") return 9;
  const index = MONTH_NAMES.findIndex(
    (name) => name.toLowerCase() === lower || name.slice(0, 3).toLowerCase() === lower,
  );
  return index === -1 ? null : index + 1;
}

/** Two-digit years: 70 to 99 are the 1900s (dates of birth), 00 to 69 are the 2000s. */
function fullYear(text: string): number | null {
  if (!/^\d{2}$|^\d{4}$/.test(text)) return null;
  const year = Number(text);
  if (text.length === 4) return year;
  return year >= 70 ? 1900 + year : 2000 + year;
}

/**
 * Reads what a person types: "1 Nov 2026", "01 november 2026", "1/11/2026", "1.11.26", "2026-11-01".
 * Numbers are day then month, the British way. Returns an ISO date, or null when it is not a real
 * date. It never guesses.
 */
export function parseUk(text: string): string | null {
  const input = text.trim();
  if (!input) return null;

  const iso = parseIso(input);
  if (iso) return toIso(iso);

  const numeric = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/.exec(input);
  if (numeric) {
    const year = fullYear(numeric[3] ?? "");
    const ymd = year === null ? null : validYmd(year, Number(numeric[2]), Number(numeric[1]));
    return ymd ? toIso(ymd) : null;
  }

  const worded = /^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$/.exec(input);
  if (worded) {
    const month = monthFromWord(worded[2] ?? "");
    const ymd = month === null ? null : validYmd(Number(worded[3]), month, Number(worded[1]));
    return ymd ? toIso(ymd) : null;
  }
  return null;
}

/** Today in the visitor's own time zone, as an ISO date. */
export function todayIso(now: Date = new Date()): string {
  return toIso({ y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() });
}

const LONDON_PARTS = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/**
 * "1 Nov 2026, 09:05" in UK time (GMT or BST, as it was on that day), whatever the visitor's own
 * time zone. Fixed on London so the server and the browser always print the same text.
 */
export function formatUkDateTime(instant: string): string {
  const date = new Date(instant);
  if (Number.isNaN(date.getTime())) return "";
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    LONDON_PARTS.formatToParts(date).find((p) => p.type === type)?.value ?? "";
  const month = MONTH_SHORT[Number(part("month")) - 1] ?? "";
  return `${Number(part("day"))} ${month} ${part("year")}, ${part("hour")}:${part("minute")}`;
}

/** The UK calendar day of an instant, as an ISO date: 00:30 BST is that day, not the one before. */
export function ukDayIso(instant: string): string {
  const date = new Date(instant);
  if (Number.isNaN(date.getTime())) return "";
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    Number(LONDON_PARTS.formatToParts(date).find((p) => p.type === type)?.value ?? 0);
  return toIso({ y: part("year"), m: part("month"), d: part("day") });
}
