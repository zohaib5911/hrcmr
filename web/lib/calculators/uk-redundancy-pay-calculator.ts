import gb from "@/rates/redundancy-gb.json";
import ni from "@/rates/redundancy-ni.json";
import niRules from "@/rates/redundancy-ni-rules.json";

export type RedundancyInput = {
  jurisdiction: "GB" | "NI";
  dateOfBirth: string;
  startDate: string;
  redundancyDate: string;
  weeklyPay: number;
  status: "employee" | "other" | "unsure";
  reason: "redundancy" | "misconduct" | "alternative" | "other";
};

export const redundancySources = [
  { ...gb, title: "GB statutory redundancy pay" },
  { ...ni, title: "Northern Ireland weekly pay limit" },
  { ...niRules, title: "Northern Ireland redundancy rules" },
].map((source) => ({
  title: source.title,
  url: source.source_url,
  checkedOn: source.checked_on,
  validFrom: source.valid_from,
  validTo: source.valid_to,
}));

function date(value: string): Date {
  const parsed = new Date(`${value}T00:00:00Z`);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
    !Number.isFinite(parsed.getTime()) ||
    parsed.toISOString().slice(0, 10) !== value
  ) {
    throw new Error("Enter valid dates.");
  }
  return parsed;
}

// Clamp leap-day anniversaries to the last day of February in a non-leap year.
function yearsBefore(value: Date, years: number): Date {
  const result = new Date(value);
  result.setUTCFullYear(value.getUTCFullYear() - years);
  if (result.getUTCMonth() !== value.getUTCMonth()) result.setUTCDate(0);
  return result;
}

function fullYears(start: Date, end: Date): number {
  const years = end.getUTCFullYear() - start.getUTCFullYear();
  return years - Number(yearsBefore(end, years) < start);
}

export function calculateRedundancy(input: RedundancyInput) {
  if (
    !["GB", "NI"].includes(input.jurisdiction) ||
    !["employee", "other", "unsure"].includes(input.status) ||
    !["redundancy", "misconduct", "alternative", "other"].includes(input.reason)
  ) {
    throw new Error("Choose valid employment details.");
  }
  const birth = date(input.dateOfBirth);
  const start = date(input.startDate);
  const end = date(input.redundancyDate);
  if (birth >= start || start > end)
    throw new Error("Dates must run from birth to employment start to redundancy.");
  if (
    !Number.isFinite(input.weeklyPay) ||
    input.weeklyPay < 0 ||
    input.weeklyPay > Number.MAX_SAFE_INTEGER / 100
  )
    throw new Error("Enter a valid non-negative weekly pay.");
  const rates = input.jurisdiction === "GB" ? gb : ni;
  const rules = input.jurisdiction === "GB" ? gb.values : niRules.values;
  if (input.redundancyDate < rates.valid_from || input.redundancyDate > rates.valid_to)
    throw new Error(`Verified rates cover ${rates.valid_from} to ${rates.valid_to} only.`);
  const serviceYears = fullYears(start, end);
  const countedYears = Math.min(serviceYears, rules.maximum_service_years);
  const weeklyPay = Math.min(input.weeklyPay, rates.values.weekly_pay_cap);
  const bands = rules.age_bands.map((band) => ({ ...band, years: 0, weeks: 0 }));
  // Count the most recent complete years backwards from the relevant date.
  // Age at the start of each completed year determines its band.
  for (let index = 0; index < countedYears; index++) {
    const age = fullYears(birth, yearsBefore(end, index + 1));
    const band = bands.find((candidate) => candidate.under === null || age < candidate.under)!;
    band.years++;
    band.weeks += band.weeks_per_year;
  }
  const message =
    input.status === "unsure" || input.reason === "other"
      ? "Eligibility needs review. Confirm employment status and the reason for leaving before relying on a payment."
      : input.status !== "employee"
        ? "Statutory redundancy pay normally requires employee status."
        : input.reason !== "redundancy"
          ? "Misconduct, being kept on, or refusing suitable alternative work without good reason normally excludes a statutory redundancy payment."
          : serviceYears < rules.minimum_service_years
            ? `At least ${rules.minimum_service_years} years of continuous employment are required.`
            : null;
  const weeks = bands.reduce((sum, band) => sum + band.weeks, 0);
  return {
    serviceYears,
    countedYears,
    weeklyPay,
    cap: rates.values.weekly_pay_cap,
    bands,
    weeks,
    eligible: message === null,
    message,
    total: message === null ? Math.round(weeks * weeklyPay * 100) / 100 : null,
  };
}
