import { describe, expect, it } from "vitest";

import {
  checkSkilledWorkerVisa,
  findOccupation,
  OCCUPATIONS,
  searchOccupations,
  type VisaInput,
} from "./skilled-worker-visa-checker";

const base: VisaInput = {
  code: "1111",
  salary: 90000,
  weeklyHours: 37.5,
  situation: "new",
  phdRelevant: false,
  phdStem: false,
  newEntrant: false,
  dependantPartner: false,
  dependantChildren: 0,
  previousSkilledWorkerBeforeJan2026: false,
};
const check = (o: Partial<VisaInput> = {}) => checkSkilledWorkerVisa({ ...base, ...o });

// Source: Appendix Skilled Occupations Table 1, 1111 going rate £88,100; 70% £61,600.
describe("skilled worker visa checker", () => {
  it("loads both tables from the verified rates file", () => {
    expect(OCCUPATIONS.length).toBeGreaterThan(200);
    expect(findOccupation("1111")?.goingRate).toBe(88100);
    expect(findOccupation("1150")?.table).toBe("1a");
  });

  it("finds occupations by title, example title and code", () => {
    expect(searchOccupations("chief executives")[0]?.code).toBe("1111");
    expect(searchOccupations("1121")[0]?.code).toBe("1121");
    expect(searchOccupations("")).toEqual([]);
  });

  it("meets option A at the going rate and fails just below it", () => {
    expect(check({ salary: 88100 }).options[0]).toMatchObject({ requiredSalary: 88100, met: true });
    expect(check({ salary: 88099 }).eligible).toBe(false);
  });

  it("uses the £41,700 general threshold when the going rate is lower", () => {
    // 1121 going rate £55,000 here; pro-rated 20h = £29,334 so the general threshold dominates.
    const r = check({ code: "1121", weeklyHours: 20, salary: 41700 });
    expect(r.options[0]).toMatchObject({ requiredSalary: 41700, met: true });
  });

  it("pro-rates the going rate by hours ÷ 37.5 (SW 14.4)", () => {
    const r = check({ weeklyHours: 18.75, salary: 44050 });
    expect(r.options[0]?.requiredSalary).toBe(44050);
    expect(r.options[0]?.met).toBe(true);
  });

  it("applies option E only for new entrants, at 70% of the going rate", () => {
    expect(check({ newEntrant: false }).options[4]?.applicable).toBe(false);
    const r = check({ newEntrant: true, salary: 61600 });
    expect(r.options[4]).toMatchObject({ applicable: true, requiredSalary: 61600, met: true });
    expect(r.eligible).toBe(true);
  });

  it("applies PhD options only when eligible occupation and answers allow", () => {
    const r = check({ phdRelevant: true, phdStem: true, salary: 70400 });
    expect(r.options[1]?.requiredSalary).toBe(79300);
    expect(r.options[2]).toMatchObject({ requiredSalary: 70400, met: true });
    expect(check().options[1]?.reason).toBe("Needs a relevant PhD");
  });

  it("scales salary for hours over 48 (SW 14.3)", () => {
    const r = check({ weeklyHours: 60, salary: 100000 });
    expect(r.salaryConsidered).toBe(80000);
    expect(r.messages.join(" ")).toContain("first 48 hours");
  });

  it("blocks Table 1a occupations for new applicants but not continuing holders", () => {
    expect(check({ code: "1150" }).eligibleOccupation).toBe(false);
    expect(check({ code: "1150", situation: "continuing", salary: 41700 }).eligible).toBe(true);
  });

  it("rejects unknown codes and missing hours", () => {
    expect(check({ code: "9999" }).eligibleOccupation).toBe(false);
    expect(check({ weeklyHours: 0 }).messages[0]).toContain("weekly hours");
  });

  it("flags Immigration Salary List codes for option D at £33,400", () => {
    const code = OCCUPATIONS.find((o) => o.onSalaryList && o.table === "1");
    expect(code).toBeDefined();
    const r = check({ code: code?.code ?? "", salary: 200000 });
    expect(r.options[3]?.applicable).toBe(true);
    expect(r.options[3]?.requiredSalary).toBeGreaterThanOrEqual(33400);
  });

  it("requires review for a recognised Table 3 nurse instead of declaring ineligibility", () => {
    // Appendix Skilled Occupations Table 3: 2231 uses option K and Table 4 pay bands.
    const result = checkSkilledWorkerVisa(
      { ...base, code: "2231" },
      {
        code: "2231",
        title: "Midwifery nurses",
      },
    );
    expect(result.status).toBe("needs-review");
    expect(result.eligibleOccupation).toBeNull();
    expect(result.options).toEqual([]);
    expect(result.lowestRequired).toBeNull();
    expect(result.messages.join(" ")).toContain("option K");
    expect(result.messages.join(" ")).not.toContain("not eligible");
    expect(check({ code: "9999" }).status).toBe("invalid-code");
    expect(check({ code: "1150" }).status).toBe("assessed");
    expect(check({ code: "1150" }).messages[0]).toContain("Table 1a");
  });

  it("does not use a stale occupation selection to recognise another code", () => {
    expect(
      checkSkilledWorkerVisa(
        { ...base, code: "9999" },
        {
          code: "2231",
          title: "Midwifery nurses",
        },
      ).status,
    ).toBe("invalid-code");
  });

  it.each([
    ["A", 0, {}, 88100],
    ["B", 1, { phdRelevant: true }, 79300],
    ["C", 2, { phdStem: true }, 70400],
    ["E", 4, { newEntrant: true }, 61600],
  ] as const)("keeps option %s salary boundaries", (_option, index, answers, salary) => {
    expect(check({ ...answers, salary }).options[index]?.met).toBe(true);
    expect(check({ ...answers, salary: salary - 1 }).options[index]?.met).toBe(false);
  });

  it("keeps the option D salary boundary", () => {
    const occupation = OCCUPATIONS.find((o) => o.onSalaryList && o.table === "1")!;
    const salary = Math.max(33400, occupation.goingRate);
    expect(check({ code: occupation.code, salary }).options[3]?.met).toBe(true);
    expect(check({ code: occupation.code, salary: salary - 1 }).options[3]?.met).toBe(false);
  });

  // SW 33.3: £285 partner, £315 first child, £200 each other child.
  it("sums dependant maintenance funds", () => {
    expect(check({ dependantPartner: true, dependantChildren: 3 }).dependantFunds).toBe(
      285 + 315 + 200 * 2,
    );
    expect(check().dependantFunds).toBe(0);
  });

  it("states B2 English, or B1 for a pre-8 January 2026 extension", () => {
    expect(check().english).toContain("B2");
    expect(check({ previousSkilledWorkerBeforeJan2026: true }).english).toContain("B1");
  });
});
