import bankHolidays from "@/rates/bank-holidays.json";
import duties from "@/rates/sponsor-duties.json";

export type Nation = "england-and-wales" | "scotland" | "northern-ireland";
export type EventKind = { id: string; label: string; days: 10 | 20 | null; clause: string };

// Periods quoted from Part 3 C1.15/C1.19 (worker changes: 10) and C2.3/C3 (organisation: 20).
export const eventKinds: readonly EventKind[] = [
  { id: "no-start", label: "Worker did not start the sponsored role", days: 10, clause: "C1.15" },
  {
    id: "absence",
    label:
      "Worker absent without permission for more than 10 consecutive working days (date of the 10th day of absence)",
    days: 10,
    clause: "C1.19",
  },
  {
    id: "unpaid",
    label: "Unpaid or reduced-pay absence passed 4 weeks in a calendar year",
    days: 10,
    clause: "C1.15",
  },
  {
    id: "salary-cut",
    label: "Worker’s salary reduced below the level on the CoS",
    days: 10,
    clause: "C1.15",
  },
  {
    id: "role",
    label: "Significant change to job role, duties or title",
    days: 10,
    clause: "C1.15 / C1.46",
  },
  { id: "location", label: "Worker’s normal work location changed", days: 10, clause: "C1.15" },
  { id: "stop", label: "You stopped sponsoring a worker", days: 10, clause: "C1.15" },
  {
    id: "offshore",
    label: "Offshore worker arrived in or left UK waters",
    days: 10,
    clause: "C1.15",
  },
  {
    id: "org-change",
    label: "Change to your organisation (date you became aware)",
    days: 20,
    clause: "C2.3",
  },
  {
    id: "insolvency",
    label: "Administration, liquidation, CVA, IVA/DAS or bankruptcy",
    days: 20,
    clause: "C3",
  },
  { id: "takeover", label: "Takeover, merger or TUPE transfer of workers", days: 20, clause: "C4" },
  {
    id: "key-personnel",
    label: "Replacing your Authorising Officer or Key Contact",
    days: null,
    clause: "C2.3",
  },
  { id: "pay-rise", label: "Salary increase", days: null, clause: "C1.15" },
];

export const sponsorDutiesSource = {
  title: "Home Office: sponsor guidance part 3 (sponsor duties and compliance)",
  url: duties.source_url,
  checkedOn: duties.checked_on,
  validFrom: duties.valid_from,
  validTo: duties.valid_to,
};
export const bankHolidaysSource = {
  title: "GOV.UK: UK bank holidays",
  url: "https://www.gov.uk/bank-holidays",
  checkedOn: bankHolidays.checked_on,
  validFrom: bankHolidays.valid_from,
  validTo: bankHolidays.valid_to,
};

export type DeadlineResult = {
  reportable: boolean;
  deadline: string | null;
  daysLeft: number | null;
  overdue: boolean;
  explanation: string[];
};

const DAY = 86_400_000;
const toTime = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const toIso = (time: number) => new Date(time).toISOString().slice(0, 10);

function validDate(value: string) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(toTime(value)) &&
    toIso(toTime(value)) === value
  );
}

export function holidaysFor(nation: Nation): Set<string> {
  return new Set(bankHolidays.nations[nation].events.map((event) => event.date));
}

export function isWorkingDay(time: number, holidays: ReadonlySet<string>) {
  const weekday = new Date(time).getUTCDay();
  return weekday !== 0 && weekday !== 6 && !holidays.has(toIso(time));
}

/** Excludes the event date and counts the last working day, as the Python API does. */
export function addWorkingDays(event: string, days: number, holidays: ReadonlySet<string>) {
  let time = toTime(event);
  for (let remaining = days; remaining > 0;) {
    time += DAY;
    if (isWorkingDay(time, holidays)) remaining -= 1;
  }
  return toIso(time);
}

/** Working days in (start, end]; negative when end is before start. */
export function workingDaysBetween(
  start: string,
  end: string,
  holidays: ReadonlySet<string>,
): number {
  if (end < start) return -workingDaysBetween(end, start, holidays);
  let total = 0;
  for (let time = toTime(start) + DAY; time <= toTime(end); time += DAY) {
    if (isWorkingDay(time, holidays)) total += 1;
  }
  return total;
}

export function calculateDeadline(input: {
  eventId: string;
  eventDate: string;
  nation: Nation;
  today: string;
}): DeadlineResult {
  const kind = eventKinds.find((item) => item.id === input.eventId);
  const none = { reportable: false, deadline: null, daysLeft: null, overdue: false };
  if (!kind) return { ...none, explanation: ["Choose an event type."] };
  if (kind.days === null) {
    return {
      ...none,
      explanation:
        kind.id === "pay-rise"
          ? [
              "The guidance does not require you to report a salary increase (unless you sponsor a Scale-up Worker). Check the paragraph cited in the sources.",
            ]
          : [
              "The 20 working day limit in C2.3 does not apply when replacing an Authorising Officer or Key Contact. Follow the SMS guidance for that change.",
            ],
    };
  }
  if (!validDate(input.eventDate))
    return { ...none, reportable: true, explanation: ["Enter the event date."] };
  const { valid_from: first, valid_to: last } = bankHolidays.nations[input.nation];
  const holidays = holidaysFor(input.nation);
  // Counted days are (start, end]; both ends must sit inside the nation's captured holidays.
  const covered = (start: string, end: string) =>
    toIso(toTime(start) + DAY) >= first && end <= last;
  const coverage = `Bank holiday dates for ${input.nation.replaceAll("-", " ")} are only held from ${first} to ${last}`;
  const deadline = addWorkingDays(input.eventDate, kind.days, holidays);
  if (!covered(input.eventDate, deadline)) {
    return {
      ...none,
      reportable: true,
      explanation: [`${coverage}, so a reliable deadline cannot be shown for this date.`],
    };
  }
  const todayValid = validDate(input.today);
  const todayCovered =
    todayValid &&
    (input.today <= deadline ? covered(input.today, deadline) : covered(deadline, input.today));
  const daysLeft = todayCovered ? workingDaysBetween(input.today, deadline, holidays) : null;
  const overdue = todayValid && input.today > deadline;
  const extra =
    todayValid && !todayCovered
      ? [`${coverage}, so working days left cannot be counted from today.`]
      : [];
  return {
    reportable: true,
    deadline,
    daysLeft,
    overdue,
    explanation: [
      `Paragraph ${kind.clause}: report within ${kind.days} working days of the event. The event day is not counted; weekends and ${input.nation.replaceAll("-", " ")} bank holidays are excluded.`,
      "Report as soon as you can: the deadline is the latest date. Confirm the trigger date against the guidance for your case.",
      ...extra,
    ],
  };
}
