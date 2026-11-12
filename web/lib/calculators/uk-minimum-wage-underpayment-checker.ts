import wages from "@/rates/minimum-wage.json";
import accommodation from "@/rates/accommodation.json";
import calculation from "@/rates/minimum-wage-calculation.json";

export const wagePeriods = wages.periods;
export const wageSources = [wages, accommodation, calculation].map((source) => ({
  title: source.title,
  url: source.source_url,
  checkedOn: source.checked_on,
  validFrom: source.valid_from,
  validTo: source.valid_to,
}));
export type WageInput = {
  payType: "time" | "salary" | "output" | "unmeasured";
  frequency: "weekly" | "fortnightly" | "four-weekly" | "monthly";
  periodStart: string;
  age: number;
  apprentice: boolean;
  firstYear: boolean;
  hours: number;
  pay: number;
  workCosts: number;
  sacrifice: number;
  tips: number;
  excludedPay: number;
  accommodationDays: number;
  accommodationCharge: number;
};
const money = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100;
export function checkMinimumWage(input: WageInput) {
  const date = new Date(`${input.periodStart}T00:00:00Z`);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(input.periodStart) ||
    !Number.isFinite(date.getTime()) ||
    date.toISOString().slice(0, 10) !== input.periodStart
  )
    throw new Error("Enter a valid pay-period start date.");
  const numbers = [
    input.hours,
    input.pay,
    input.workCosts,
    input.sacrifice,
    input.tips,
    input.excludedPay,
    input.accommodationDays,
    input.accommodationCharge,
  ];
  if (
    numbers.some((n) => !Number.isFinite(n) || n < 0) ||
    input.hours === 0 ||
    !Number.isInteger(input.age) ||
    input.age < 16 ||
    !Number.isInteger(input.accommodationDays)
  )
    throw new Error(
      "Enter non-negative amounts, positive hours, whole accommodation days and an age of at least 16. Confirm school-leaving age eligibility separately.",
    );
  if (
    !["time", "salary", "output", "unmeasured"].includes(input.payType) ||
    !["weekly", "fortnightly", "four-weekly", "monthly"].includes(input.frequency)
  )
    throw new Error("Choose a pay type and frequency.");
  const nextMonth = new Date(date);
  nextMonth.setUTCMonth(nextMonth.getUTCMonth() + 1, 1);
  const daysInMonth = new Date(
    Date.UTC(nextMonth.getUTCFullYear(), nextMonth.getUTCMonth(), 0),
  ).getUTCDate();
  const maxDays = { weekly: 7, fortnightly: 14, "four-weekly": 28, monthly: daysInMonth }[
    input.frequency
  ];
  if (
    input.accommodationDays > maxDays ||
    (input.accommodationDays === 0 && input.accommodationCharge > 0)
  )
    throw new Error("Check accommodation days and charges for this pay period.");
  const period = wagePeriods.find(
    (p) => input.periodStart >= p.valid_from && input.periodStart <= p.valid_to,
  );
  if (!period) throw new Error("No verified wage rates cover this pay-period start date.");
  const bands = period.age_band_rates as Record<string, number | undefined>;
  const band =
    input.apprentice && (input.age < period.apprentice_under_age || input.firstYear)
      ? "Apprentice"
      : input.age < 18
        ? "Under 18"
        : input.age < 21
          ? "18 to 20"
          : Object.keys(bands).find(
              (key) =>
                key !== "Apprentice" &&
                Number(key.split(" ")[0]) <= input.age &&
                (key.includes("over") || input.age <= Number(key.split(" ").at(-1))),
            );
  const rate = band ? bands[band] : undefined;
  if (rate === undefined) throw new Error("No verified age band applies.");
  const offset = accommodation.periods.find(
    (p) => input.periodStart >= p.valid_from && input.periodStart <= p.valid_to,
  );
  if (input.accommodationDays && !offset)
    throw new Error("No verified accommodation offset covers this period.");
  const allowance = money((offset?.daily ?? 0) * input.accommodationDays);
  const adjustment =
    input.accommodationCharge === 0
      ? allowance
      : Math.min(0, money(allowance - input.accommodationCharge));
  const countedPay = money(
    input.pay - input.workCosts - input.sacrifice - input.tips - input.excludedPay + adjustment,
  );
  const requiredPay = rate * input.hours;
  const deficit = Math.max(0, requiredPay - countedPay);
  if (![countedPay, requiredPay, countedPay / input.hours].every(Number.isFinite))
    throw new Error("Enter smaller amounts.");
  return {
    band,
    rate,
    countedPay,
    hourlyRate: countedPay / input.hours,
    belowMinimum: deficit > 0.00000001,
    shortfall: Math.ceil(Math.max(0, deficit - 0.00000001) * 100) / 100,
    adjustment,
    period,
  };
}
