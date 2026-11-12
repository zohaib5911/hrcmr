import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  calculateTakeHome,
  type TakeHomeInput,
} from "@/lib/calculators/uk-take-home-salary-calculator";

const base: TakeHomeInput = {
  taxYear: "2026-2027",
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

  // Hand-worked: £30,000 times the code's flat rate, without an allowance.
  // Code meanings: GOV.UK /tax-codes/what-your-tax-code-means;
  // percentages: GOV.UK /guidance/rates-and-thresholds-for-employers-2026-to-2027.
  it.each([
    ["england", "BR", 6000],
    ["england", "D0", 12000],
    ["england", "D1", 13500],
    ["wales", "BR", 6000],
    ["wales", "CBR", 6000],
    ["wales", "D0", 12000],
    ["wales", "CD0", 12000],
    ["wales", "D1", 13500],
    ["wales", "CD1", 13500],
    ["scotland", "BR", 6000],
    ["scotland", "SBR", 6000],
    ["scotland", "SD0", 6300],
    ["scotland", "SD1", 12600],
    ["scotland", "SD2", 13500],
    ["scotland", "SD3", 14400],
    ["england", "NT", 0],
    ["wales", "NT", 0],
    ["scotland", "NT", 0],
  ] as const)("maps %s code %s explicitly", (region, taxCode, tax) => {
    expect(get({ ...base, region, taxCode }, "Income tax")).toBe(-tax);
  });

  it.each([
    ["england", "0T", 6000],
    ["wales", "C0T", 6000],
    ["scotland", "S0T", 6090.77],
  ] as const)("uses no allowance for %s %s", (region, taxCode, tax) => {
    expect(get({ ...base, region, taxCode }, "Income tax")).toBe(-tax);
  });

  it("keeps zero-allowance codes progressive across the higher-rate boundary", () => {
    // £37,700 × 20% + £22,300 × 40% = £16,460, with no allowance.
    expect(get({ ...base, salary: 60000, taxCode: "0T" }, "Income tax")).toBe(-16460);
    expect(get({ ...base, region: "wales", salary: 60000, taxCode: "C0T" }, "Income tax")).toBe(
      -16460,
    );
  });

  it.each([
    ["england", "SBR"],
    ["england", "CD0"],
    ["england", "SD1"],
    ["england", "S1257L"],
    ["england", "C0T"],
    ["wales", "S0T"],
    ["wales", "SD1"],
    ["wales", "CD2"],
    ["scotland", "CD1"],
    ["scotland", "D0"],
    ["scotland", "D1"],
    ["scotland", "SD4"],
    ["scotland", "SNT"],
    ["scotland", "SAUTO"],
    ["england", "1257L W1"],
    ["england", "1257L M1"],
    ["england", "1257LX"],
    ["england", "1257Y"],
    ["england", "D2"],
  ] as const)("rejects unsupported %s code %s", (region, taxCode) => {
    expect(calculateTakeHome({ ...base, region, taxCode })).toBeNull();
  });

  it("preserves regional numeric codes, normalization and other-jobs basic rate", () => {
    expect(get({ ...base, region: "scotland", taxCode: "S1000L" }, "Income tax")).toBe(
      get({ ...base, region: "scotland", taxCode: "1000L" }, "Income tax"),
    );
    expect(get({ ...base, region: "wales", taxCode: "C1000L" }, "Income tax")).toBe(-3998.2);
    expect(get({ ...base, region: "scotland", taxCode: " sd1 " }, "Income tax")).toBe(-12600);
    expect(get({ ...base, region: "scotland", otherJobs: true }, "Income tax")).toBe(-6000);
  });

  it.each([
    ["plan 1", 1254.15, 1179],
    ["plan 2", 1037.7, 955.35],
    ["plan 4", 652.95, 558.45],
  ] as const)("uses each year's %s threshold", (studentLoan, oldLoan, newLoan) => {
    expect(get({ ...base, taxYear: "2025-2026", salary: 40000, studentLoan }, "Student loan")).toBe(
      -oldLoan,
    );
    expect(get({ ...base, salary: 40000, studentLoan }, "Student loan")).toBe(-newLoan);
  });

  it("uses the selected year's Scottish bands and identifies the year", () => {
    // 2025: 2,827 × 19% + (14,921 - 2,827) × 20% + (17,430 - 14,921) × 21%.
    const input = { ...base, taxYear: "2025-2026" as const, region: "scotland" as const };
    expect(get(input, "Income tax")).toBe(-3482.82);
    expect(get(input, "National Insurance")).toBe(-1394.4);
    expect(calculateTakeHome(input)?.notes[0]).toContain("2025 to 2026");
    expect(get({ ...input, taxYear: "2026-2027" }, "Income tax")).toBe(-3451.07);
  });

  it("rejects unsupported years and Plan 5 in 2025–26", () => {
    expect(
      calculateTakeHome({ ...base, taxYear: "2024-2025" as TakeHomeInput["taxYear"] }),
    ).toBeNull();
    expect(calculateTakeHome({ ...base, taxYear: "2025-2026", studentLoan: "plan 5" })).toBeNull();
    expect(get({ ...base, studentLoan: "plan 5" }, "Student loan")).toBe(-450);
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
