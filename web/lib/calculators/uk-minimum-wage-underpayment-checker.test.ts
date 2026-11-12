import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { checkMinimumWage, type WageInput } from "./uk-minimum-wage-underpayment-checker";
const base: WageInput = {
  payType: "time",
  frequency: "weekly",
  periodStart: "2026-04-01",
  age: 21,
  apprentice: false,
  firstYear: false,
  hours: 40,
  pay: 508.4,
  workCosts: 0,
  sacrifice: 0,
  tips: 0,
  excludedPay: 0,
  accommodationDays: 0,
  accommodationCharge: 0,
};
describe("minimum wage", () => {
  // Official apprentice examples: https://www.gov.uk/national-minimum-wage-rates
  it.each([
    [true, 8],
    [false, 12.71],
  ])("uses first-year apprentice status %s", (firstYear, rate) => {
    expect(checkMinimumWage({ ...base, apprentice: true, firstYear }).rate).toBe(rate);
  });
  // Official shift allowance example: https://www.gov.uk/guidance/calculating-the-minimum-wage/calculating-the-minimum-wage
  it("excludes the premium in the official 2025 example", () => {
    const r = checkMinimumWage({
      ...base,
      periodStart: "2025-06-01",
      age: 25,
      pay: 252,
      hours: 20,
      excludedPay: 9,
    });
    expect(r.hourlyRate).toBe(12.15);
    expect(r.shortfall).toBe(1.2);
  });
  // Hand-worked arithmetic from web/rates/minimum-wage.json, matching API test_minimum_wage.py boundaries.
  it.each([
    [20, "2026-04-01", 10.85],
    [21, "2026-04-01", 12.71],
    [17, "2026-04-01", 8],
    [30, "2026-03-31", 12.21],
    [30, "2027-04-01", 13.21],
    [22, "2023-04-01", 10.18],
    [24, "2020-04-01", 8.2],
  ])("selects age %s on %s", (age, periodStart, rate) =>
    expect(checkMinimumWage({ ...base, age, periodStart }).rate).toBe(rate),
  );
  // Hand-worked using https://www.gov.uk/national-minimum-wage-accommodation: 7 × £11.10 = £77.70.
  it.each([
    [0, 77.7],
    [50, 0],
    [100, -22.3],
  ])("handles accommodation charge %s", (accommodationCharge, adjustment) => {
    expect(
      checkMinimumWage({ ...base, accommodationDays: 7, accommodationCharge }).adjustment,
    ).toBe(adjustment);
  });
  // Hand-worked: 508.40 - 10 costs - 20 sacrifice - 30 tips = 448.40; deficit £60.
  it("removes costs, sacrifice and tips once", () =>
    expect(checkMinimumWage({ ...base, workCosts: 10, sacrifice: 20, tips: 30 }).shortfall).toBe(
      60,
    ));
  // Hand-worked: £508.39 / 40 rounds visually to £12.71 but remains underpaid by 1p.
  it("does not round hourly pay before comparison", () => {
    const r = checkMinimumWage({ ...base, pay: 508.39 });
    expect(r.belowMinimum).toBe(true);
    expect(r.shortfall).toBe(0.01);
  });
  it("accepts exact compliance", () => expect(checkMinimumWage(base).belowMinimum).toBe(false));
  it.each([
    { hours: 0 },
    { pay: -1 },
    { hours: Infinity },
    { age: 15 },
    { periodStart: "2026-02-30" },
    { periodStart: "2099-01-01" },
    { accommodationDays: 8 },
    { periodStart: "2027-04-01", accommodationDays: 7 },
  ])("rejects invalid or unverified inputs %j", (patch) =>
    expect(() => checkMinimumWage({ ...base, ...patch })).toThrow(),
  );
  it("has no transport or persistence", () => {
    for (const path of [
      "lib/calculators/uk-minimum-wage-underpayment-checker.ts",
      "components/calculators/uk-minimum-wage-underpayment-checker.tsx",
    ])
      expect(readFileSync(path, "utf8")).not.toMatch(
        /fetch\s*\(|localStorage|sessionStorage|sendBeacon|XMLHttpRequest/,
      );
  });
});
