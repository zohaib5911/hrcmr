import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  allOccupations,
  calculateIlrSalary,
  prorate,
  searchOccupations,
  thresholds,
} from "./skilled-worker-ilr-salary-calculator";

const occ = (code: string) => {
  const found = allOccupations.find((o) => o.code === code);
  if (!found) throw new Error(`missing ${code}`);
  return found;
};

describe("skilled worker ILR salary calculator", () => {
  // https://www.gov.uk/indefinite-leave-to-remain-tier-2-t2-skilled-worker-visa/salary-requirements
  it("reads the fixed thresholds from the rates file", () => {
    expect(thresholds).toMatchObject({
      standard: 41_700,
      salaryList: 33_400,
      transitional: 31_300,
      transitionalSalaryList: 25_000,
      sportsperson: 35_800,
    });
  });

  // Hand-worked from the rates file: 1111 going rate £88,100 is higher than £41,700.
  it("uses the higher of the minimum and the standard going rate", () => {
    const r = calculateIlrSalary({ occupation: occ("1111"), situation: "standard", hours: 37.5 });
    expect(r.fullTimeGoingRate).toBe(88_100);
    expect(r.required).toBe(88_100);
  });

  // Hand-worked: 2136 going rate £41,200 is below £41,700, so the minimum applies.
  it("uses £41,700 when the going rate is lower", () => {
    const r = calculateIlrSalary({ occupation: occ("2136"), situation: "standard", hours: 37.5 });
    expect(r.required).toBe(41_700);
  });

  // Hand-worked: £88,100 × 30 / 37.5 = £70,480; the £41,700 minimum is not pro-rated.
  it("pro-rates the going rate by hours but not the minimum", () => {
    expect(prorate(88_100, 30)).toBe(70_480);
    const r = calculateIlrSalary({ occupation: occ("1111"), situation: "standard", hours: 30 });
    expect(r.required).toBe(70_480);
    const low = calculateIlrSalary({ occupation: occ("2136"), situation: "standard", hours: 20 });
    expect(low.required).toBe(41_700);
  });

  // Hand-worked from the rates file: Immigration Salary List minimum is £33,400.
  it("applies the salary list and transitional thresholds", () => {
    expect(
      calculateIlrSalary({ occupation: occ("2136"), situation: "salary_list", hours: 37.5 })
        .required,
    ).toBe(41_200);
    const t = calculateIlrSalary({
      occupation: occ("2136"),
      situation: "transitional",
      hours: 37.5,
    });
    expect(t.required).toBe(34_500);
    expect(t.floor).toBe(31_300);
  });

  it("handles sportspeople and national pay-scale jobs", () => {
    expect(
      calculateIlrSalary({ occupation: occ("1111"), situation: "standard", hours: 37.5 }).basis,
    ).toBe("Usual salary requirement");
    expect(
      calculateIlrSalary({ occupation: occ("1111"), situation: "sportsperson", hours: 10 })
        .required,
    ).toBe(35_800);
    const scale = allOccupations.find((o) => o.payScale);
    expect(scale).toBeDefined();
    const r = calculateIlrSalary({ occupation: scale!, situation: "standard", hours: 37.5 });
    expect(r.required).toBeNull();
    expect(r.notes.join(" ")).toContain("£25,000");
  });

  it("searches by code and by words", () => {
    expect(searchOccupations("1111")[0]?.code).toBe("1111");
    expect(searchOccupations("chief executives").map((o) => o.code)).toContain("1111");
    expect(searchOccupations("  ")).toEqual([]);
  });

  it("never sends or stores anything", () => {
    const source = readFileSync(
      new URL("./skilled-worker-ilr-salary-calculator.ts", import.meta.url),
      "utf8",
    );
    expect(source).not.toMatch(
      /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
    );
  });
});
