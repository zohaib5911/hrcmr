import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { calculateSickPay, type SickPayInput } from "./uk-sick-pay-calculator";

// No official worked example exists for the 2026 rules. Hand-worked arithmetic from
// https://www.gov.uk/statutory-sick-pay/what-youll-get (£123.25 cap, 80% of earnings, 28 weeks)
// https://www.gov.uk/government/publications/employer-bulletin-february-2026/february-2026-issue-of-the-employer-bulletin
const base: SickPayInput = {
  employeeStatus: "employee",
  startDate: "2026-06-01", // Monday
  endDate: "2026-06-07", // Sunday
  qualifyingDays: [1, 2, 3, 4, 5],
  weeklyEarnings: 400,
};
describe("sick pay calculator", () => {
  it("pays from day one at the weekly cap when 80% of earnings exceeds it", () => {
    // 80% × 400 = 320 > 123.25, so cap applies: 5 days × 24.65 = 123.25.
    expect(calculateSickPay(base)).toMatchObject({
      weeklyRate: 123.25,
      dailyRate: 24.65,
      payableDays: 5,
      total: 123.25,
    });
  });
  it("uses 80% of earnings when lower than the cap, with no lower earnings limit", () => {
    // 80% × 100 = 80; 3 days of 5 → 3 × 16 = 48.
    const result = calculateSickPay({ ...base, weeklyEarnings: 100, endDate: "2026-06-03" });
    expect(result).toMatchObject({ weeklyRate: 80, dailyRate: 16, payableDays: 3, total: 48 });
  });
  it("builds a week-by-week table and ignores non-qualifying days", () => {
    const result = calculateSickPay({ ...base, endDate: "2026-06-10" });
    expect(result.weeks).toEqual([
      { week: 1, from: "2026-06-01", to: "2026-06-07", payableDays: 5, amount: 123.25 },
      { week: 2, from: "2026-06-08", to: "2026-06-10", payableDays: 3, amount: 73.95 },
    ]);
  });
  it("stops at 28 weeks", () => {
    const result = calculateSickPay({ ...base, endDate: "2027-03-01" });
    expect(result.payableDays).toBe(140);
    expect(result.maxReached).toBe(true);
    expect(result.total).toBe(3451);
  });
  it("returns not eligible for non-employees", () => {
    expect(calculateSickPay({ ...base, employeeStatus: "other" })).toMatchObject({
      eligible: false,
      total: 0,
    });
  });
  it("rejects invalid input and pre-reform absences", () => {
    expect(() => calculateSickPay({ ...base, endDate: "2026-05-01" })).toThrow(/Check the dates/);
    expect(() => calculateSickPay({ ...base, qualifyingDays: [] })).toThrow();
    expect(() => calculateSickPay({ ...base, weeklyEarnings: -1 })).toThrow();
    expect(() =>
      calculateSickPay({ ...base, startDate: "2026-04-01", endDate: "2026-04-10" }),
    ).toThrow(/6 April 2026/);
  });
  it("does not store or transmit answers", () => {
    const source = readFileSync(
      path.join(process.cwd(), "lib/calculators/uk-sick-pay-calculator.ts"),
      "utf8",
    );
    expect(source).not.toMatch(/fetch\(|localStorage|sessionStorage|XMLHttpRequest/);
  });
});
