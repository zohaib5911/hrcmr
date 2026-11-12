import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  calculateTakeHome,
  type TakeHomeInput,
} from "@/lib/calculators/uk-take-home-salary-calculator";

const base: TakeHomeInput = {
  region: "england",
  salary: 30000,
  taxCode: "auto",
  pensionMethod: "none",
  pensionPercent: 0,
  studentLoan: "none",
  postgradLoan: false,
  niCategory: "A",
  otherJobs: false,
  benefits: 0,
  otherDeductions: 0,
};
const get = (input: TakeHomeInput, label: string) =>
  calculateTakeHome(input)?.rows.find((r) => r.label === label)?.annual;

// No official worked example: hand-worked from web/rates/payroll-2026-27.json.
// Tax (30,000 - 12,570) x 20% = 3,486.00; NI (30,000 - 12,570) x 8% = 1,394.40.
describe("take-home salary calculator", () => {
  it("England, £30,000, category A", () => {
    const r = calculateTakeHome(base)!;
    expect(get(base, "Income tax")).toBe(-3486);
    expect(get(base, "National Insurance")).toBe(-1394.4);
    expect(r.annual).toBe(25119.6);
    expect(r.monthly).toBe(2093.3);
    expect(r.weekly).toBe(483.07);
  });

  // Hand-worked: higher rate. Taxable 60,000 - 12,570 = 47,430: 37,700 x 20% + 9,730 x 40% = 11,432.
  // NI: (50,270 - 12,570) x 8% + 9,730 x 2% = 3,016 + 194.60 = 3,210.60.
  it("applies higher-rate tax and the NI upper earnings limit", () => {
    const input = { ...base, salary: 60000 };
    expect(get(input, "Income tax")).toBe(-11432);
    expect(get(input, "National Insurance")).toBe(-3210.6);
  });

  // Hand-worked: Scotland £30,000, taxable 17,430 over bands 3,967@19%, to 16,956@20%, rest@21%.
  // 753.73 + 2,597.80 + 0.21 x 474 = 99.54 -> 3,451.07
  it("uses Scottish bands", () => {
    expect(get({ ...base, region: "scotland" }, "Income tax")).toBe(-3451.07);
  });

  // Hand-worked: loan 9% over 29,385 at £40,000 = 955.35; postgraduate 6% over 21,000 = 1,140.
  it("deducts student and postgraduate loans", () => {
    const input = { ...base, salary: 40000, studentLoan: "plan 2" as const, postgradLoan: true };
    expect(get(input, "Student loan")).toBe(-955.35);
    expect(get(input, "Postgraduate loan")).toBe(-1140);
  });

  // Hand-worked: 5% net pay of 30,000 = 1,500 off taxable pay, not off NI.
  it("handles pension methods", () => {
    const netPay = { ...base, pensionMethod: "net_pay" as const, pensionPercent: 5 };
    expect(get(netPay, "Income tax")).toBe(-3186);
    expect(get(netPay, "National Insurance")).toBe(-1394.4);
    const sacrifice = { ...base, pensionMethod: "salary_sacrifice" as const, pensionPercent: 5 };
    expect(get(sacrifice, "National Insurance")).toBe(-1274.4);
  });

  it("handles custom codes, other jobs and the allowance taper", () => {
    expect(get({ ...base, taxCode: "1000L" }, "Income tax")).toBe(-3998.2);
    expect(get({ ...base, otherJobs: true }, "Income tax")).toBe(-6000);
    expect(get({ ...base, salary: 125140 }, "Income tax")).toBe(
      -(37700 * 0.2 + (125140 - 37700) * 0.4),
    );
  });

  it("rejects invalid input", () => {
    expect(calculateTakeHome({ ...base, salary: 0 })).toBeNull();
    expect(calculateTakeHome({ ...base, taxCode: "ZZ" })).toBeNull();
    expect(calculateTakeHome({ ...base, niCategory: "Q" })).toBeNull();
  });

  it("makes no network or storage calls", () => {
    const source = readFileSync("lib/calculators/uk-take-home-salary-calculator.ts", "utf8");
    expect(source).not.toMatch(/fetch\(|localStorage|sessionStorage|XMLHttpRequest/);
  });
});
