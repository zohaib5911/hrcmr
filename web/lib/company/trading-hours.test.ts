import { describe, expect, it } from "vitest";

import { dayProblem, hhmm, openSummary } from "./trading-hours";

describe("trading hours", () => {
  it("trims seconds", () => {
    expect(hhmm("09:00:00")).toBe("09:00");
    expect(hhmm(null)).toBeNull();
  });
  it("refuses times that cannot be saved", () => {
    expect(dayProblem("09:00", "17:30")).toBeNull();
    expect(dayProblem(null, "17:30")).not.toBeNull();
    expect(dayProblem("17:00", "09:00")).not.toBeNull();
    expect(dayProblem("09:00", "09:00")).not.toBeNull();
  });
  it("summarises the week", () => {
    expect(openSummary([{ is_open: false }])).toBe("Not set yet");
    expect(openSummary([{ is_open: true }, { is_open: false }])).toBe("Open 1 day a week");
    expect(openSummary([{ is_open: true }, { is_open: true }])).toBe("Open 2 days a week");
  });
});
