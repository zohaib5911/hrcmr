import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { calculateRedundancy, type RedundancyInput } from "./uk-redundancy-pay-calculator";

const base: RedundancyInput = {
  jurisdiction: "NI",
  dateOfBirth: "1996-11-12",
  startDate: "2016-11-12",
  redundancyDate: "2026-11-12",
  weeklyPay: 450,
  status: "employee",
  reason: "redundancy",
};

describe("statutory redundancy pay", () => {
  // https://www.nidirect.gov.uk/articles/redundancy-pay — official worked example two.
  it("reproduces the age-30 variable-hours example: 8 + 2 × 0.5 weeks", () => {
    expect(calculateRedundancy(base)).toMatchObject({ weeks: 9, total: 4050, serviceYears: 10 });
  });
  // Same official source, example three: five years × £325 = £1,625.
  it("reproduces the age-35 average weekly pay example", () => {
    expect(
      calculateRedundancy({
        ...base,
        dateOfBirth: "1991-11-12",
        startDate: "2021-11-12",
        weeklyPay: 325,
      }).total,
    ).toBe(1625);
  });
  // Same source, example one's £600 input conflicts with its £783 multiplication.
  // Hand-work the stated £600 wage: (4 × 1.5 + 11) × £600 = £10,200.
  it("uses actual pay below the cap despite the inconsistent official example one", () => {
    expect(
      calculateRedundancy({
        ...base,
        dateOfBirth: "1981-11-12",
        startDate: "2011-11-12",
        weeklyPay: 600,
      }),
    ).toMatchObject({ weeks: 17, total: 10200 });
  });
  // https://www.gov.uk/redundancy-your-rights/redundancy-pay and NI source above.
  // Hand-worked maximum: 20 × 1.5 × each jurisdiction's cap.
  it.each([
    ["GB", 751, 22530],
    ["NI", 783, 23490],
  ] as const)("caps %s pay and service", (jurisdiction, cap, total) => {
    expect(
      calculateRedundancy({
        ...base,
        jurisdiction,
        dateOfBirth: "1960-11-12",
        startDate: "1980-11-12",
        weeklyPay: 1000,
      }),
    ).toMatchObject({ countedYears: 20, weeks: 30, weeklyPay: cap, total });
  });
  // Hand-worked age boundary cases from the same official age bands.
  it.each([
    [22, 1],
    [23, 1.5],
    [24, 2],
    [41, 2],
    [42, 2.5],
    [43, 3],
  ])("age %i with two full years yields %s weeks", (age, weeks) => {
    expect(
      calculateRedundancy({ ...base, dateOfBirth: `${2026 - age}-11-12`, startDate: "2024-11-12" })
        .weeks,
    ).toBe(weeks);
  });
  // Hand-worked service boundary from the official two-year eligibility rule.
  it("requires two completed years", () => {
    expect(calculateRedundancy({ ...base, startDate: "2024-11-13" })).toMatchObject({
      serviceYears: 1,
      eligible: false,
      total: null,
    });
    expect(calculateRedundancy({ ...base, startDate: "2024-11-12" }).eligible).toBe(true);
  });
  // Calendar regression: leap days must not roll into March.
  it("counts leap-day and partial-year service consistently", () => {
    expect(
      calculateRedundancy({ ...base, startDate: "2024-02-29", redundancyDate: "2027-02-28" })
        .serviceYears,
    ).toBe(2);
    expect(calculateRedundancy({ ...base, startDate: "2020-12-01" }).serviceYears).toBe(5);
  });
  it.each([
    { status: "other" },
    { status: "unsure" },
    { reason: "misconduct" },
    { reason: "alternative" },
    { reason: "other" },
  ] as Partial<RedundancyInput>[])(
    "does not quote a payment for excluded or uncertain details %j",
    (change) => {
      expect(calculateRedundancy({ ...base, ...change })).toMatchObject({
        eligible: false,
        total: null,
      });
    },
  );
  it.each([
    { weeklyPay: -1 },
    { weeklyPay: NaN },
    { weeklyPay: Infinity },
    { dateOfBirth: "2026-02-30" },
    { startDate: "bad" },
    { startDate: "2027-01-01" },
    { dateOfBirth: "2020-01-01" },
    { redundancyDate: "2026-04-05" },
    { redundancyDate: "2027-04-06" },
  ])("rejects invalid or unsupported inputs %j", (change) => {
    expect(() => calculateRedundancy({ ...base, ...change })).toThrow();
  });
  it("accepts both ends of the verified rate period and zero pay", () => {
    for (const redundancyDate of ["2026-04-06", "2027-04-05"]) {
      expect(calculateRedundancy({ ...base, redundancyDate, weeklyPay: 0 }).total).toBe(0);
    }
  });
  it("contains no input transport or persistence", () => {
    for (const file of [
      "../../lib/calculators/uk-redundancy-pay-calculator.ts",
      "../../components/calculators/uk-redundancy-pay-calculator.tsx",
    ]) {
      const code = readFileSync(new URL(file, import.meta.url), "utf8");
      expect(code).not.toMatch(
        /\b(fetch|XMLHttpRequest|localStorage|sessionStorage|sendBeacon|indexedDB|WebSocket)\b|document\.cookie/,
      );
    }
  });
});
