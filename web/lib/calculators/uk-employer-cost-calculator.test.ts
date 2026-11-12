import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  calculateEmployerCost,
  employerCostYears,
  type EmployerCostInput,
} from "./uk-employer-cost-calculator";

const base: EmployerCostInput = {
  taxYear: "2026-2027",
  salary: 30000,
  age: 30,
  employeeType: "standard",
  pensionRate: 3,
  pensionBasis: "qualifying",
};
// No official combined-cost worked example exists. Hand-worked arithmetic from:
// https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027
// https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2025-to-2026
// https://www.gov.uk/workplace-pensions/what-you-your-employer-and-the-government-pay
// These sources apply to every scenario in this suite.
describe("employer cost: sourced annual budget examples", () => {
  it.each(["2025-2026", "2026-2027"] as const)("%s: £30,000 salary", (taxYear) => {
    // NI (30,000 - 5,000) × 15% = 3,750; pension (30,000 - 6,240) × 3% = 712.80.
    expect(calculateEmployerCost({ ...base, taxYear })).toMatchObject({
      category: "A",
      niThreshold: 5000,
      employerNI: 3750,
      pensionableEarnings: 23760,
      employerPension: 712.8,
      totalCost: 34462.8,
      levyRate: 0.005,
      levyAllowance: 15000,
      levyPayBillThreshold: 3000000,
    });
  });
  it.each([
    ["standard", 20, "M", 0],
    ["standard", 21, "A", 8250],
    ["apprentice", 24, "H", 1459.5],
    ["apprentice", 25, "A", 8250],
    ["standard", 70, "A", 8250],
  ] as const)("%s age %s uses %s", (employeeType, age, category, expectedNI) => {
    // At £60,000, relieved NI = (60,000 - 50,270) × 15%; age 20 case uses £30,000.
    const salary = age === 20 ? 30000 : 60000;
    expect(calculateEmployerCost({ ...base, salary, age, employeeType })).toMatchObject({
      category,
      employerNI: expectedNI,
    });
  });
  it.each([0, 4999, 5000])("no NI up to the secondary threshold: %s", (salary) => {
    expect(calculateEmployerCost({ ...base, salary }).employerNI).toBe(0);
  });
  it.each(["standard", "apprentice"] as const)(
    "relieved threshold boundary: %s",
    (employeeType) => {
      expect(
        calculateEmployerCost({ ...base, age: 20, employeeType, salary: 50270 }).employerNI,
      ).toBe(0);
      expect(
        calculateEmployerCost({ ...base, age: 20, employeeType, salary: 50271 }).employerNI,
      ).toBe(0.15);
    },
  );
  it.each([
    [0, 0],
    [6240, 0],
    [6241, 0.03],
    [50270, 1320.9],
    [100000, 1320.9],
  ])("qualifying pension salary %s", (salary, expected) => {
    expect(calculateEmployerCost({ ...base, salary }).employerPension).toBe(expected);
  });
  it("full salary pension is uncapped and uses the chosen rate", () => {
    // 60,000 × 5% = 3,000; NI = 8,250; total = 71,250.
    expect(
      calculateEmployerCost({ ...base, salary: 60000, pensionRate: 5, pensionBasis: "full" }),
    ).toMatchObject({ employerPension: 3000, totalCost: 71250 });
  });
  it("zero pension is explicit and does not remove NI", () => {
    expect(calculateEmployerCost({ ...base, pensionRate: 0 })).toMatchObject({
      employerPension: 0,
      employerNI: 3750,
      totalCost: 33750,
    });
  });
  it.each([
    { salary: -1 },
    { salary: NaN },
    { salary: Infinity },
    { salary: Number.MAX_VALUE },
    { age: -1 },
    { age: 20.5 },
    { age: Infinity },
    { pensionRate: -1 },
    { pensionRate: 101 },
    { pensionRate: NaN },
    { taxYear: "2027-2028" },
    { taxYear: "toString" },
    { employeeType: "contractor" },
    { pensionBasis: "unknown" },
  ])("rejects unsupported or invalid inputs: %j", (override) => {
    expect(() => calculateEmployerCost({ ...base, ...override } as EmployerCostInput)).toThrow();
  });
  it("normalized relief ages match the captured HMRC labels for both years", () => {
    for (const data of Object.values(employerCostYears)) {
      const labels = Object.keys(data.values.ni_thresholds);
      expect(labels).toContain(
        `Upper secondary threshold (under ${data.values.employer_ni_under_age})`,
      );
      expect(labels).toContain(
        `Apprentice upper secondary threshold (apprentice under ${data.values.employer_ni_apprentice_under_age})`,
      );
    }
  });
  it("does not store or transmit input from either calculation or form", () => {
    for (const file of [
      "lib/calculators/uk-employer-cost-calculator.ts",
      "components/calculators/uk-employer-cost-calculator.tsx",
    ]) {
      const source = readFileSync(path.resolve(process.cwd(), file), "utf8");
      expect(source).not.toMatch(
        /\b(fetch|XMLHttpRequest|localStorage|sessionStorage|indexedDB|sendBeacon|WebSocket)\b|document\.cookie/,
      );
    }
  });
});
