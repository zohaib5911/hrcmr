import { describe, expect, it } from "vitest";

import {
  addWorkingDays,
  calculateDeadline,
  holidaysFor,
  workingDaysBetween,
} from "./sponsor-reporting-deadline-calculator";

// Same cases as api/tests/test_working_days.py.
describe("working days", () => {
  it.each([
    ["2026-08-28", 10, ["2026-08-31"], "2026-09-14"],
    ["2026-08-28", 20, ["2026-08-31"], "2026-09-28"],
    ["2026-07-31", 10, ["2026-08-03"], "2026-08-17"],
    ["2026-07-31", 10, [], "2026-08-14"],
    ["2026-03-13", 10, ["2026-03-17"], "2026-03-30"],
    ["2026-04-02", 10, ["2026-04-03", "2026-04-06"], "2026-04-20"],
    ["2026-12-24", 10, ["2026-12-25", "2026-12-28", "2027-01-01"], "2027-01-12"],
    ["2026-08-29", 1, ["2026-08-31"], "2026-09-01"],
    ["2026-08-29", 0, [], "2026-08-29"],
  ])("%s + %i days", (event, days, hols, expected) => {
    const set = new Set(hols as string[]);
    expect(addWorkingDays(event as string, days as number, set)).toBe(expected);
    expect(workingDaysBetween(event as string, expected as string, set)).toBe(days);
  });

  it("signs reversed ranges and ignores weekends", () => {
    const hols = new Set(["2026-08-31"]);
    expect(workingDaysBetween("2026-09-01", "2026-08-28", hols)).toBe(-1);
    expect(workingDaysBetween("2026-09-04", "2026-09-05", hols)).toBe(0);
  });
});

describe("calculateDeadline", () => {
  const base = { nation: "england-and-wales" as const, today: "2026-08-28" };
  it("uses 10 days for worker changes and the published bank holidays", () => {
    const result = calculateDeadline({ ...base, eventId: "role", eventDate: "2026-08-28" });
    expect(result).toMatchObject({
      reportable: true,
      deadline: "2026-09-14",
      daysLeft: 10,
      overdue: false,
    });
  });
  it("uses 20 days for organisation changes", () => {
    expect(
      calculateDeadline({ ...base, eventId: "org-change", eventDate: "2026-08-28" }).deadline,
    ).toBe("2026-09-28");
  });
  it("differs by nation", () => {
    const scot = calculateDeadline({
      ...base,
      nation: "scotland",
      eventId: "role",
      eventDate: "2026-07-31",
    });
    const ew = calculateDeadline({ ...base, eventId: "role", eventDate: "2026-07-31" });
    expect(scot.deadline).toBe("2026-08-17");
    expect(ew.deadline).toBe("2026-08-14");
    expect(holidaysFor("scotland").has("2026-08-03")).toBe(true);
  });
  it("flags overdue", () => {
    const r = calculateDeadline({
      ...base,
      today: "2026-09-20",
      eventId: "role",
      eventDate: "2026-08-28",
    });
    expect(r.overdue).toBe(true);
    expect(r.daysLeft).toBeLessThan(0);
  });
  it("handles non-reportable and invalid input", () => {
    expect(
      calculateDeadline({ ...base, eventId: "pay-rise", eventDate: "2026-08-28" }).reportable,
    ).toBe(false);
    expect(
      calculateDeadline({ ...base, eventId: "role", eventDate: "2026-02-30" }).deadline,
    ).toBeNull();
    expect(
      calculateDeadline({ ...base, eventId: "role", eventDate: "2028-12-20" }).deadline,
    ).toBeNull();
  });
});
