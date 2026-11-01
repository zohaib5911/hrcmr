/** Time entry for TimePicker: 24-hour "HH:MM" (plan 5.8), tolerant of how people type. */

export function formatTime(hours: number, minutes: number): string {
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

/** "9", "930", "9.30", "9:30", "5pm", "12:15 am" all become "HH:MM"; anything else is null. */
export function parseTime(text: string): string | null {
  const input = text.trim().toLowerCase();
  const meridiem = /\s*(am|pm)$/.exec(input);
  const body = meridiem ? input.slice(0, meridiem.index) : input;

  let hours: number;
  let minutes = 0;
  const colon = /^(\d{1,2})[:.](\d{2})$/.exec(body);
  const compact = /^(\d{1,2})(\d{2})$/.exec(body);
  const bare = /^\d{1,2}$/.exec(body);
  if (colon) {
    hours = Number(colon[1]);
    minutes = Number(colon[2]);
  } else if (compact && body.length >= 3) {
    hours = Number(compact[1]);
    minutes = Number(compact[2]);
  } else if (bare) {
    hours = Number(body);
  } else {
    return null;
  }

  if (minutes > 59) return null;
  if (meridiem) {
    if (hours < 1 || hours > 12) return null;
    hours = (hours % 12) + (meridiem[1] === "pm" ? 12 : 0);
  }
  if (hours > 23) return null;
  return formatTime(hours, minutes);
}

/** Moves by `step` minutes and stays inside the day. An empty field starts at 09:00. */
export function stepTime(value: string | null, step: number, direction: 1 | -1): string {
  const current = value ? parseTime(value) : null;
  if (!current) return "09:00";
  const [h = 0, m = 0] = current.split(":").map(Number);
  const total = Math.min(Math.max(h * 60 + m + direction * step, 0), 23 * 60 + 59);
  return formatTime(Math.floor(total / 60), total % 60);
}
