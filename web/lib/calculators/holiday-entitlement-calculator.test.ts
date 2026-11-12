import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { calculateHoliday, roundUpToHalf, statutoryDays } from "./holiday-entitlement-calculator";

describe("holiday entitlement calculator", () => {
  // https://www.gov.uk/holiday-entitlement-rights (5-day week = 28 days; 3 days a week = 16.8 days)
  it.each([
    [5, 28, false],
    [3, 16.8, false],
    [6, 28, true],
    [2.5, 14, false],
  ])("%d days a week gives %d days", (daysPerWeek, days, capped) => {
    const result = calculateHoliday({ mode: "days", daysPerWeek });
    expect(result).toMatchObject({ unit: "days", entitlement: days, capped });
    expect(statutoryDays(daysPerWeek).days).toBe(days);
  });

  // Hand-worked from web/rates/holiday.json: 37.5 hours × 5.6 = 210 hours.
  it("hours per week × 5.6", () => {
    expect(calculateHoliday({ mode: "hours", hoursPerWeek: 37.5 })).toMatchObject({
      unit: "hours",
      entitlement: 210,
    });
  });

  // https://www.gov.uk/holiday-entitlement-rights/calculate-leave-entitlement
  // 30 hours worked in a pay period earns 3.621 hours, rounded to 4 hours.
  it("irregular hours accrue at 12.07% and round to the nearest hour", () => {
    expect(calculateHoliday({ mode: "irregular", hoursWorked: 30 })).toMatchObject({
      unit: "hours",
      entitlement: 4,
    });
    // Hand-worked: 4 hours × 12.07% = 0.4828 → 0; 5 hours × 12.07% = 0.6035 → 1.
    expect(calculateHoliday({ mode: "irregular", hoursWorked: 4 })?.entitlement).toBe(0);
    expect(calculateHoliday({ mode: "irregular", hoursWorked: 5 })?.entitlement).toBe(1);
  });

  it("rounds up to the nearest half day", () => {
    expect(roundUpToHalf(2.33)).toBe(2.5);
    expect(roundUpToHalf(2.5)).toBe(2.5);
    expect(roundUpToHalf(2.51)).toBe(3);
  });

  // Hand-worked (day proportion, not the GOV.UK month method): 28 × 184 ÷ 365 = 14.12 → 14.5 days.
  it("part-year start: pro-rata by days in the leave year", () => {
    const result = calculateHoliday({
      mode: "part_year",
      daysPerWeek: 5,
      leaveYearStart: "2027-01-01",
      leaveYearEnd: "2027-12-31",
      startDate: "2027-07-01",
      endDate: "2027-12-31",
    });
    expect(result).toMatchObject({ unit: "days", entitlement: 14.5 });
    expect(result?.workings.length).toBeGreaterThan(1);
  });

  it("rejects invalid input", () => {
    expect(calculateHoliday({ mode: "days", daysPerWeek: 0 })).toBeNull();
    expect(calculateHoliday({ mode: "days", daysPerWeek: 8 })).toBeNull();
    expect(calculateHoliday({ mode: "hours", hoursPerWeek: -1 })).toBeNull();
    expect(calculateHoliday({ mode: "irregular", hoursWorked: Number.NaN })).toBeNull();
    expect(
      calculateHoliday({
        mode: "part_year",
        daysPerWeek: 5,
        leaveYearStart: "2027-01-01",
        leaveYearEnd: "2027-12-31",
        startDate: "bad",
        endDate: "2027-12-31",
      }),
    ).toBeNull();
  });

  it("keeps calculator code free of transport and persistence", () => {
    const source = readFileSync(
      new URL("./holiday-entitlement-calculator.ts", import.meta.url),
      "utf8",
    );
    expect(source).not.toMatch(
      /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
    );
  });
});
