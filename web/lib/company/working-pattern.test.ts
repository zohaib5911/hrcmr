import { describe, expect, it } from "vitest";

import { weekSummary } from "./working-pattern";

const week = (working: number[], hours = 8) =>
  [1, 2, 3, 4, 5, 6, 7].map((weekday) => ({
    weekday,
    is_working: working.includes(weekday),
    hours: working.includes(weekday) ? hours : 0,
  }));

describe("weekSummary", () => {
  it("describes the week in a few words", () => {
    expect(weekSummary(week([1, 2, 3, 4, 5]))).toBe("Mon to Fri, 40 hours");
    expect(weekSummary(week([1, 3, 5], 7.5))).toBe("Mon, Wed and Fri, 22.5 hours");
    expect(weekSummary(week([2]))).toBe("Tue, 8 hours");
    expect(weekSummary(week([6, 7], 4))).toBe("Sat and Sun, 8 hours");
    expect(weekSummary(week([]))).toBe("no working days");
  });
});
