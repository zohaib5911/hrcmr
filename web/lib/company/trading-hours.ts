/** The API sends "09:00:00"; the page works in "09:00". */
export function hhmm(value: string | null | undefined): string | null {
  return value ? value.slice(0, 5) : null;
}

/** What is wrong with an open day's times, or null when they can be saved. */
export function dayProblem(opens: string | null, closes: string | null): string | null {
  if (!opens || !closes) return "Say when it opens and when it closes.";
  if (opens >= closes) return "It must open before it closes.";
  return null;
}

/** The opening a day gets when it is switched on, until the person changes it. */
export const SUGGESTED_OPENING = { opens: "09:00", closes: "17:00" } as const;

/** "Open 5 days a week", "Open 7 days a week", or "Not set yet". */
export function openSummary(days: readonly { is_open: boolean }[]): string {
  const open = days.filter((day) => day.is_open).length;
  if (open === 0) return "Not set yet";
  return `Open ${open} ${open === 1 ? "day" : "days"} a week`;
}
