import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { calculateSickPay, type SickPayInput } from "./uk-sick-pay-calculator";

// Partial-week amounts match HMRC's 2026–27 SSP payment table (rates/payroll-2026-27.json,
// https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027). Other figures
// are hand-worked from
// https://www.gov.uk/statutory-sick-pay/what-youll-get (£123.25 cap, 80% of earnings, 28 weeks)
// https://www.gov.uk/government/publications/employer-bulletin-february-2026/february-2026-issue-of-the-employer-bulletin
const base: SickPayInput = {
  employeeStatus: "employee",
  startDate: "2026-06-01", // Monday
  endDate: "2026-06-07", // Sunday
  qualifyingDays: [1, 2, 3, 4, 5],
  weeklyEarnings: 400,
  workedPartOfFirstDay: false,
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
      { week: 1, from: "2026-06-01", to: "2026-06-06", payableDays: 5, amount: 123.25 },
      { week: 2, from: "2026-06-07", to: "2026-06-10", payableDays: 3, amount: 73.95 },
    ]);
  });
  it("matches HMRC's published partial-week payment table", () => {
    const all = [0, 1, 2, 3, 4, 5, 6];
    // 7 qualifying days, 2 days (Mon–Tue) = £35.22; 6 qualifying days, 4 days (Mon–Thu) = £82.17.
    expect(calculateSickPay({ ...base, qualifyingDays: all, endDate: "2026-06-02" }).total).toBe(
      35.22,
    );
    expect(
      calculateSickPay({ ...base, qualifyingDays: [1, 2, 3, 4, 5, 6], endDate: "2026-06-04" })
        .total,
    ).toBe(82.17);
  });
  it("splits a midweek absence at Sunday and rounds each SSP week", () => {
    // Thu 4 – Mon 8 June, 7 qualifying days: Thu–Sat 3 days £52.83, Sun–Mon 2 days £35.22.
    const result = calculateSickPay({
      ...base,
      qualifyingDays: [0, 1, 2, 3, 4, 5, 6],
      startDate: "2026-06-04",
      endDate: "2026-06-08",
    });
    expect(result.weeks).toEqual([
      { week: 1, from: "2026-06-04", to: "2026-06-06", payableDays: 3, amount: 52.83 },
      { week: 2, from: "2026-06-07", to: "2026-06-08", payableDays: 2, amount: 35.22 },
    ]);
    expect(result.total).toBe(88.05);
  });
  it("does not pay a first day partly worked", () => {
    const result = calculateSickPay({ ...base, workedPartOfFirstDay: true });
    expect(result).toMatchObject({ payableDays: 4, total: 98.6 });
    expect(result.weeks[0]?.from).toBe("2026-06-02");
    expect(
      calculateSickPay({ ...base, workedPartOfFirstDay: true, endDate: "2026-06-01" }),
    ).toMatchObject({ payableDays: 0, total: 0, weeks: [] });
  });
  it("rejects absences beyond the verified 2026–27 rate year", () => {
    expect(() => calculateSickPay({ ...base, endDate: "2027-04-06" })).toThrow(/5 April 2027/);
    expect(calculateSickPay({ ...base, endDate: "2027-04-05" }).maxReached).toBe(true);
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
