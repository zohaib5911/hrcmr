export const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

const SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

/** "Mon to Fri, 40 hours", "Mon, Wed and Fri, 22.5 hours", or "no working days". */
export function weekSummary(
  days: readonly { weekday: number; is_working: boolean; hours: number }[],
): string {
  const working = days.filter((day) => day.is_working).sort((a, b) => a.weekday - b.weekday);
  if (working.length === 0) return "no working days";
  const total = working.reduce((sum, day) => sum + day.hours, 0);
  const hours = `${Number.isInteger(total) ? total : total.toFixed(1)} hours`;
  const names = working.map((day) => SHORT[day.weekday - 1]);
  const consecutive = working.every(
    (day, index) => index === 0 || day.weekday === (working[index - 1]?.weekday ?? 0) + 1,
  );
  if (working.length > 2 && consecutive) {
    return `${names[0]} to ${names[names.length - 1]}, ${hours}`;
  }
  const last = names.pop();
  return `${names.length > 0 ? `${names.join(", ")} and ` : ""}${last}, ${hours}`;
}
