import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  calculateNotice,
  completedYears,
  hasOneMonth,
  statutoryNoticeWeeks,
  type NoticeInput,
} from "./uk-notice-pay-calculator";

// Scale: https://www.gov.uk/redundancy-your-rights/notice-periods (hand-worked from rates file; GOV.UK has no worked example).
describe("statutory notice", () => {
  it.each([
    ["2026-10-20", 0], // under one month
    ["2026-10-01", 1], // exactly one month
    ["2025-01-01", 1], // 1 year, under 2
    ["2024-11-12", 2], // exactly 2 years
    ["2020-06-01", 6], // 6 complete years
    ["2010-01-01", 12], // 16 years, capped
  ])("employer notice, start %s => %i weeks", (start, weeks) => {
    expect(statutoryNoticeWeeks("employer", "employee", start, "2026-11-12")).toBe(weeks);
  });

  it("employee giving notice needs one week after one month", () => {
    // https://www.gov.uk/handing-in-your-notice/giving-notice
    expect(statutoryNoticeWeeks("employee", "employee", "2010-01-01", "2026-11-12")).toBe(1);
    expect(statutoryNoticeWeeks("employee", "employee", "2026-11-01", "2026-11-12")).toBe(0);
  });

  it("workers have no statutory notice", () => {
    expect(statutoryNoticeWeeks("employer", "worker", "2010-01-01", "2026-11-12")).toBe(0);
  });

  it("counts years and months on anniversaries", () => {
    expect(completedYears("2024-11-13", "2026-11-12")).toBe(1);
    expect(completedYears("2024-11-12", "2026-11-12")).toBe(2);
    expect(hasOneMonth("2026-10-12", "2026-11-12")).toBe(true);
    expect(hasOneMonth("2026-10-13", "2026-11-12")).toBe(false);
  });
});

const base: NoticeInput = {
  jurisdiction: "gb",
  giver: "employer",
  status: "employee",
  startDate: "2020-06-01",
  noticeDate: "2026-11-12",
  contractWeeks: null,
  payMode: "weekly",
  amount: 500,
  arrangement: "pilon",
};

// Hand-worked: 6 complete years => 6 weeks x £500 = £3,000; 12 Nov 2026 + 42 days = 24 Dec 2026.
describe("calculateNotice", () => {
  it("uses statutory when the contract is silent", () => {
    const r = calculateNotice(base);
    expect(r).toMatchObject({ ok: true, noticeWeeks: 6, noticePay: 3000, lastDay: "2026-12-24" });
  });

  it("uses a longer contractual period", () => {
    const r = calculateNotice({ ...base, contractWeeks: 8 });
    expect(r).toMatchObject({ ok: true, noticeWeeks: 8, noticePay: 4000 });
  });

  it("an employer cannot give less than statutory", () => {
    const r = calculateNotice({ ...base, contractWeeks: 2 });
    expect(r).toMatchObject({ ok: true, noticeWeeks: 6 });
  });

  it("converts annual pay to weekly (£52,000 / 52 = £1,000)", () => {
    const r = calculateNotice({ ...base, payMode: "annual", amount: 52000, contractWeeks: 4 });
    expect(r).toMatchObject({ ok: true, weeklyPay: 1000, noticePay: 6000 });
  });

  it("employee resigning follows the contract", () => {
    const r = calculateNotice({ ...base, giver: "employee", contractWeeks: 4 });
    expect(r).toMatchObject({ ok: true, statutoryWeeks: 1, noticeWeeks: 4, noticePay: 2000 });
  });

  it("garden leave and PILON notes differ", () => {
    const g = calculateNotice({ ...base, arrangement: "garden-leave" });
    const p = calculateNotice(base);
    expect(g.ok && g.notes.join(" ")).toContain("garden leave");
    expect(p.ok && p.notes.join(" ")).toContain("PILON");
  });

  it("rejects bad input", () => {
    expect(calculateNotice({ ...base, noticeDate: "2019-01-01" })).toMatchObject({ ok: false });
    expect(calculateNotice({ ...base, amount: 0 })).toMatchObject({ ok: false });
    expect(calculateNotice({ ...base, startDate: "" })).toMatchObject({ ok: false });
    expect(calculateNotice({ ...base, contractWeeks: 1.5 })).toMatchObject({ ok: false });
  });
});

describe("privacy", () => {
  it("never sends or stores anything", () => {
    const src = readFileSync(new URL("./uk-notice-pay-calculator.ts", import.meta.url), "utf8");
    expect(src).not.toMatch(/fetch\(|XMLHttpRequest|localStorage|sessionStorage|sendBeacon/);
  });
});
