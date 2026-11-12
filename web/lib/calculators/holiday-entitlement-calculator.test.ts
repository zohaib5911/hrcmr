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
  it("hours per week × 5.6 for a five-day week", () => {
    expect(
      calculateHoliday({ mode: "hours", hoursPerWeek: 37.5, daysPerWeek: 5, equalDays: true }),
    ).toMatchObject({ unit: "hours", entitlement: 210, capped: false });
  });

  // GOV.UK /holiday-entitlement-rights: six-day workers are capped at 28 days.
  // 45 h ÷ 6 = 7.5 h a day; 6 × 5.6 = 33.6 days → 28 days × 7.5 h = 210 h (not 252 h).
  it("applies the 28-day cap to hours over six days", () => {
    const result = calculateHoliday({
      mode: "hours",
      hoursPerWeek: 45,
      daysPerWeek: 6,
      equalDays: true,
    });
    expect(result).toMatchObject({ unit: "hours", entitlement: 210, capped: true });
    expect(result?.workings).toContain("Capped at the statutory maximum of 28 days.");
    expect(result?.workings).toContain("28 days × 7.5 hours = 210 hours");
  });

  // Part time: 22.5 h over 3 days = 7.5 h a day; 3 × 5.6 = 16.8 days × 7.5 = 126 h.
  it("part-time hours match 5.6 weeks of the hours", () => {
    expect(
      calculateHoliday({ mode: "hours", hoursPerWeek: 22.5, daysPerWeek: 3, equalDays: true }),
    ).toMatchObject({ entitlement: 126, capped: false });
  });

  it.each([3, 5, 6, 7])("days and hours modes agree for %s days a week", (daysPerWeek) => {
    const days = calculateHoliday({ mode: "days", daysPerWeek })!;
    const hours = calculateHoliday({
      mode: "hours",
      hoursPerWeek: daysPerWeek * 8,
      daysPerWeek,
      equalDays: true,
    })!;
    expect(hours.entitlement).toBeCloseTo(days.entitlement * 8, 6);
    expect(hours.capped).toBe(days.capped);
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
    const hours = { mode: "hours", hoursPerWeek: 37.5, daysPerWeek: 5, equalDays: true } as const;
    expect(calculateHoliday({ ...hours, hoursPerWeek: -1 })).toBeNull();
    expect(calculateHoliday({ ...hours, daysPerWeek: Number.NaN })).toBeNull();
    expect(calculateHoliday({ ...hours, daysPerWeek: 8 })).toBeNull();
    expect(calculateHoliday({ ...hours, equalDays: false })).toBeNull();
    expect(calculateHoliday({ ...hours, hoursPerWeek: 50, daysPerWeek: 2 })).toBeNull();
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
