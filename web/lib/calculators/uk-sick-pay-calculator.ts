import sickChanges from "@/rates/sick-changes.json";
import sickEligibility from "@/rates/sick-eligibility.json";
import sickPay from "@/rates/sick-pay.json";

export type SickPayInput = {
  employeeStatus: "employee" | "agency" | "other";
  startDate: string; // YYYY-MM-DD, first day of sickness absence
  endDate: string; // YYYY-MM-DD, last day of sickness absence (inclusive)
  qualifyingDays: number[]; // Weekdays worked normally, 0 = Sunday … 6 = Saturday
  weeklyEarnings: number; // Average weekly earnings over the 8-week reference period
};
export type SickPayWeek = {
  week: number;
  from: string;
  to: string;
  payableDays: number;
  amount: number;
};
export const sickPaySources = [sickPay, sickChanges, sickEligibility].map((source) => ({
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
    Math.min(v.weekly_cap, input.weeklyEarnings * v.average_weekly_earnings_rate),
  );
  const dailyRate = weeklyRate / days.length;
  const maxDays = v.maximum_weeks * days.length;
  const weeks: SickPayWeek[] = [];
  let paid = 0;
  let maxReached = false;
  for (let offset = 0, week = 1; addDays(start, offset) <= end; offset += 7, week += 1) {
    let payable = 0;
    const weekStart = addDays(start, offset);
    let weekEnd = weekStart;
    for (let i = 0; i < 7 && addDays(weekStart, i) <= end; i += 1) {
      const day = addDays(weekStart, i);
      weekEnd = day;
      if (!days.includes(day.getUTCDay())) continue;
      if (paid + payable >= maxDays) {
        maxReached = true;
        continue;
      }
      payable += 1;
    }
    paid += payable;
    weeks.push({
      week,
      from: iso(weekStart),
      to: iso(weekEnd),
      payableDays: payable,
      amount: money(payable * dailyRate),
    });
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
