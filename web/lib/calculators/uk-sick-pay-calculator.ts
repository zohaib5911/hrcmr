import sickChanges from "@/rates/sick-changes.json";
import sickEligibility from "@/rates/sick-eligibility.json";
import payroll from "@/rates/payroll-2026-27.json";
import sickPay from "@/rates/sick-pay.json";

export type SickPayInput = {
  employeeStatus: "employee" | "agency" | "other";
  startDate: string; // YYYY-MM-DD, first day of sickness absence
  endDate: string; // YYYY-MM-DD, last day of sickness absence (inclusive)
  qualifyingDays: number[]; // Weekdays worked normally, 0 = Sunday … 6 = Saturday
  weeklyEarnings: number; // Average weekly earnings over the 8-week reference period
  workedPartOfFirstDay: boolean; // A worked part-day is not a full day of sickness, so is not paid
};
export type SickPayWeek = {
  week: number;
  from: string;
  to: string;
  payableDays: number;
  amount: number;
};
export const sickPaySources = [payroll, sickPay, sickChanges, sickEligibility].map((source) => ({
  title: source.title,
  url: source.source_url,
  checkedOn: source.checked_on,
  validFrom: source.valid_from,
  validTo: source.valid_to,
}));
const money = (amount: number) => Math.round((amount + Number.EPSILON) * 100) / 100;
const parse = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value ? null : date;
};
const iso = (date: Date) => date.toISOString().slice(0, 10);
const addDays = (date: Date, days: number) => new Date(date.getTime() + days * 86_400_000);
const rateYearEnd = new Date(`${payroll.valid_to}T00:00:00Z`);
/**
 * HMRC's 2026–27 SSP payment table (payroll-2026-27.json) pays the unrounded daily rate
 * × days, rounded up to the next penny (e.g. 7 qualifying days, 2 days = £35.22; 6 days,
 * 4 days = £82.17). The SSP manual's prose example rounds the daily rate first (£82.16);
 * we follow the dated payment table. Whole pennies avoid floating-point drift.
 */
const partWeekPay = (weeklyPence: number, days: number, qualifying: number) =>
  Math.ceil((weeklyPence * days) / qualifying) / 100;

/** SSP under the rules for absences starting on or after the reform commencement date. */
export function calculateSickPay(input: SickPayInput) {
  const start = parse(input.startDate);
  const end = parse(input.endDate);
  const days = [...new Set(input.qualifyingDays)];
  if (
    !start ||
    !end ||
    end < start ||
    days.length === 0 ||
    days.some((day) => !Number.isInteger(day) || day < 0 || day > 6) ||
    !Number.isFinite(input.weeklyEarnings) ||
    input.weeklyEarnings < 0 ||
    !["employee", "agency", "other"].includes(input.employeeStatus)
  )
    throw new Error(
      "Check the dates (end on or after start), qualifying days and average weekly earnings.",
    );
  if (start < new Date(`${sickChanges.valid_from}T00:00:00Z`))
    throw new Error(
      "This calculator only covers absences starting on or after 6 April 2026. Earlier absences follow the old rules (waiting days and lower earnings limit); check GOV.UK.",
    );
  if (end > rateYearEnd)
    throw new Error(
      "This calculator only has verified SSP rates for 6 April 2026 to 5 April 2027. Enter a last day on or before 5 April 2027, or check GOV.UK for later rates.",
    );
  if (input.employeeStatus === "other")
    return {
      eligible: false as const,
      reason:
        "SSP is for employees (and some agency workers). Self-employed people and others are not eligible.",
      weeklyRate: 0,
      dailyRate: 0,
      payableDays: 0,
      total: 0,
      weeks: [] as SickPayWeek[],
      maxReached: false,
    };

  const v = sickPay.values;
  const weeklyRate = money(
    Math.min(payroll.values.ssp_weekly_cap, input.weeklyEarnings * v.average_weekly_earnings_rate),
  );
  const weeklyPence = Math.round(weeklyRate * 100);
  const dailyRate = weeklyRate / days.length;
  const maxDays = v.maximum_weeks * days.length;
  const weeks: SickPayWeek[] = [];
  let paid = 0;
  let maxReached = false;
  // SSP weeks run Sunday to Saturday; the first and last rows can be part weeks.
  let weekStart = input.workedPartOfFirstDay ? addDays(start, 1) : start;
  for (let week = 1; weekStart <= end; week += 1) {
    let payable = 0;
    let weekEnd = weekStart;
    for (let day = weekStart; day <= end; day = addDays(day, 1)) {
      weekEnd = day;
      if (days.includes(day.getUTCDay())) {
        if (paid + payable >= maxDays) maxReached = true;
        else payable += 1;
      }
      if (day.getUTCDay() === 6) break;
    }
    paid += payable;
    weeks.push({
      week,
      from: iso(weekStart),
      to: iso(weekEnd),
      payableDays: payable,
      amount: partWeekPay(weeklyPence, payable, days.length),
    });
    weekStart = addDays(weekEnd, 1);
  }
  return {
    eligible: true as const,
    reason: "",
    weeklyRate,
    dailyRate: money(dailyRate),
    payableDays: paid,
    total: money(weeks.reduce((sum, w) => sum + w.amount, 0)),
    weeks,
    maxReached,
  };
}
