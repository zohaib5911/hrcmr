import accrual from "@/rates/holiday-accrual.json";
import holiday from "@/rates/holiday.json";

export type HolidayMode = "days" | "hours" | "part_year" | "irregular";
export type Unit = "days" | "hours";

export type HolidayInput =
  | { mode: "days"; daysPerWeek: number }
  | { mode: "hours"; hoursPerWeek: number }
  | {
      mode: "part_year";
      daysPerWeek: number;
      leaveYearStart: string; // YYYY-MM-DD
      leaveYearEnd: string;
      startDate: string; // first day in the job (or leave year start)
      endDate: string; // last day in the job (or leave year end)
    }
  | { mode: "irregular"; hoursWorked: number };

export type HolidayResult = {
  unit: Unit;
  entitlement: number;
  capped: boolean;
  workings: string[];
};

const H = holiday.values;
const A = accrual.values;

export const holidaySources = [holiday, accrual].map((file) => ({
  title: file.title,
  url: file.source_url,
  checkedOn: file.checked_on,
  validFrom: file.valid_from,
  validTo: file.valid_to,
}));

const DAY_MS = 86_400_000;
const parse = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
const inclusiveDays = (from: string, to: string) =>
  Math.round((parse(to) - parse(from)) / DAY_MS) + 1;
// Avoid floating-point noise such as 16.799999999999997.
const clean = (value: number) => Math.round(value * 1e6) / 1e6;
export const roundUpToHalf = (value: number) => Math.ceil(clean(value) * 2) / 2;

function validDays(days: number) {
  return Number.isFinite(days) && days > 0 && days <= 7;
}

/** Statutory entitlement in days for a regular week of `days` days (capped at 28). */
export function statutoryDays(daysPerWeek: number): { days: number; capped: boolean } {
  const raw = clean(daysPerWeek * H.statutory_weeks);
  return raw > H.maximum_statutory_days
    ? { days: H.maximum_statutory_days, capped: true }
    : { days: raw, capped: false };
}

export function calculateHoliday(input: HolidayInput): HolidayResult | null {
  switch (input.mode) {
    case "days": {
      if (!validDays(input.daysPerWeek)) return null;
      const { days, capped } = statutoryDays(input.daysPerWeek);
      return {
        unit: "days",
        entitlement: days,
        capped,
        workings: [
          `${input.daysPerWeek} days × ${H.statutory_weeks} weeks = ${clean(input.daysPerWeek * H.statutory_weeks)} days`,
          ...(capped
            ? [`Capped at the statutory maximum of ${H.maximum_statutory_days} days.`]
            : []),
        ],
      };
    }
    case "hours": {
      if (
        !Number.isFinite(input.hoursPerWeek) ||
        input.hoursPerWeek <= 0 ||
        input.hoursPerWeek > 168
      )
        return null;
      const hours = clean(input.hoursPerWeek * H.statutory_weeks);
      return {
        unit: "hours",
        entitlement: hours,
        capped: false,
        workings: [`${input.hoursPerWeek} hours × ${H.statutory_weeks} weeks = ${hours} hours`],
      };
    }
    case "part_year": {
      if (!validDays(input.daysPerWeek)) return null;
      const dates = [input.leaveYearStart, input.leaveYearEnd, input.startDate, input.endDate];
      if (dates.some((d) => !/^\d{4}-\d{2}-\d{2}$/.test(d) || Number.isNaN(parse(d)))) return null;
      const yearDays = inclusiveDays(input.leaveYearStart, input.leaveYearEnd);
      const from =
        parse(input.startDate) < parse(input.leaveYearStart)
          ? input.leaveYearStart
          : input.startDate;
      const to =
        parse(input.endDate) > parse(input.leaveYearEnd) ? input.leaveYearEnd : input.endDate;
      const employed = inclusiveDays(from, to);
      if (yearDays < 1 || employed < 1 || employed > yearDays) return null;
      const { days: full } = statutoryDays(input.daysPerWeek);
      const proportion = employed / yearDays;
      const entitlement = roundUpToHalf(full * proportion);
      return {
        unit: "days",
        entitlement,
        capped: false,
        workings: [
          `Full-year entitlement: ${full} days.`,
          `Employed ${employed} of ${yearDays} days in the leave year (${(proportion * 100).toFixed(1)}%).`,
          `${full} × ${employed} ÷ ${yearDays} = ${clean(full * proportion).toFixed(2)}, rounded up to the nearest half day = ${entitlement} days.`,
        ],
      };
    }
    case "irregular": {
      if (!Number.isFinite(input.hoursWorked) || input.hoursWorked < 0) return null;
      const raw = clean(input.hoursWorked * A.irregular_part_year_accrual_rate);
      const entitlement = Math.floor(raw + 0.5); // nearest whole hour, 0.5 rounds up
      return {
        unit: "hours",
        entitlement,
        capped: false,
        workings: [
          `${input.hoursWorked} hours × ${(A.irregular_part_year_accrual_rate * 100).toFixed(2)}% = ${raw.toFixed(3)} hours`,
          `Rounded to the nearest whole hour (0.5 rounds up) = ${entitlement} hours.`,
        ],
      };
    }
  }
}
