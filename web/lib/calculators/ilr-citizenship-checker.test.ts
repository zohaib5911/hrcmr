import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { checkSettlement, settlementRoutes, type SettlementInput } from "./ilr-citizenship-checker";

const base: SettlementInput = {
  route: "skilled_worker",
  startDate: "2021-06-20",
  residenceStart: "2021-06-20",
  settledDate: "",
  britishSpouse: false,
  rollingAbsences: 0,
  citizenshipAbsences: 0,
  lastYearAbsences: 0,
};
const calc = (input: Partial<SettlementInput> = {}) => checkSettlement({ ...base, ...input });

describe("settlement and citizenship milestones", () => {
  // Hand-worked anniversaries using GOV.UK sources embedded in each rates route; no official combined timeline example exists.
  it.each([
    ["skilled_worker", "2026-06-20"],
    ["health_care", "2026-06-20"],
    ["scale_up", "2026-06-20"],
    ["ancestry", "2026-06-20"],
    ["innovator", "2024-06-20"],
    ["talent_3", "2024-06-20"],
    ["talent_5", "2026-06-20"],
    ["family_2", "2023-06-20"],
    ["family_5", "2026-06-20"],
    ["family_10", "2031-06-20"],
    ["long_residence", "2031-06-20"],
    ["bno", "2026-06-20"],
    ["investor", "2026-06-20"],
    ["entrepreneur", "2026-06-20"],
  ])("%s full qualifying anniversary is %s", (route, date) => {
    expect(calc({ route }).qualifyingDate).toBe(date);
    expect(settlementRoutes).toHaveLength(14);
  });

  // https://www.gov.uk/apply-citizenship-indefinite-leave-to-remain: hand-worked 5-year residence + 12 months holding ILR.
  it("separates predicted settlement from the actual grant", () => {
    expect(calc().citizenshipDate).toBe("2027-06-20");
    expect(calc().indicative).toBe(true);
    expect(calc({ settledDate: "2026-11-15" }).citizenshipDate).toBe("2027-11-15");
    expect(calc({ settledDate: "2026-11-15" }).indicative).toBe(false);
  });

  // https://www.gov.uk/apply-citizenship-spouse: hand-worked, 3 years residence and no post-settlement wait.
  it("requires the spouse residence minimum even on a shorter settlement route", () => {
    expect(calc({ route: "family_2", britishSpouse: true }).citizenshipDate).toBe("2024-06-20");
    expect(calc({ britishSpouse: true, settledDate: "2026-11-15" }).citizenshipDate).toBe(
      "2026-11-15",
    );
  });

  // https://www.gov.uk/apply-citizenship-indefinite-leave-to-remain: 5-year residence is independent of the settlement route start.
  it("honours earlier UK residence and the longer standard citizenship period", () => {
    expect(calc({ route: "innovator" }).citizenshipDate).toBe("2026-06-20");
    expect(calc({ route: "innovator", residenceStart: "2019-06-20" }).citizenshipDate).toBe(
      "2025-06-20",
    );
  });

  // https://www.gov.uk/guidance/immigration-rules/immigration-rules-appendix-continuous-residence: 180 days, exceptions need review.
  it("flags exceeded rolling absence limits without moving an eligibility date", () => {
    expect(calc({ rollingAbsences: 180 }).settlementReview).toBe(false);
    expect(calc({ rollingAbsences: 181 }).settlementReview).toBe(true);
    expect(calc({ route: "long_residence" }).settlementReview).toBe(true);
    expect(calc({ route: "family_5", rollingAbsences: 181 }).notes.join(" ")).toMatch(
      /individual review/,
    );
  });

  // https://www.gov.uk/apply-citizenship-indefinite-leave-to-remain and https://www.gov.uk/apply-citizenship-spouse: published absence limits.
  it.each([
    [false, 450, 90, false],
    [false, 451, 90, true],
    [false, 450, 91, true],
    [true, 270, 90, false],
    [true, 271, 90, true],
    [true, 270, 91, true],
  ])(
    "citizenship absences spouse=%s total=%i last year=%i review=%s",
    (britishSpouse, citizenshipAbsences, lastYearAbsences, expected) => {
      expect(calc({ britishSpouse, citizenshipAbsences, lastYearAbsences }).citizenshipReview).toBe(
        expected,
      );
    },
  );

  // Hand-worked calendar boundary using the same GOV.UK qualifying periods (no official leap-day example).
  it("clamps leap-day anniversaries and uses UTC", () => {
    expect(calc({ startDate: "2020-02-29", residenceStart: "2020-02-29" }).qualifyingDate).toBe(
      "2025-02-28",
    );
  });

  // Input integrity rather than a legal worked example.
  it.each([
    { startDate: "2021-02-29" },
    { startDate: "" },
    { route: "unknown" },
    { residenceStart: "2022-06-20" },
    { settledDate: "2019-01-01" },
    { settledDate: "2026-02-30" },
    { rollingAbsences: -1 },
    { citizenshipAbsences: NaN },
    { lastYearAbsences: 0.5 },
    { lastYearAbsences: 1, citizenshipAbsences: 0 },
  ])("rejects invalid answers %j", (input) => {
    expect(() => calc(input)).toThrow();
  });

  it("has no transport or persistence", () => {
    const source = readFileSync(new URL("./ilr-citizenship-checker.ts", import.meta.url), "utf8");
    expect(source).not.toMatch(
      /fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|document\.cookie/,
    );
  });
});
