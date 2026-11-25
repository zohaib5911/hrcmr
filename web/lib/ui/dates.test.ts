import { describe, expect, it } from "vitest";

import {
  addDays,
  ukDayIso,
  addMonths,
  compareIso,
  daysInMonth,
  formatUk,
  formatUkDateTime,
  formatUkLong,
  isoWeekdayIndex,
  monthGrid,
  parseIso,
  parseUk,
  startOfWeek,
  todayIso,
} from "./dates";

describe("parseIso", () => {
  it("accepts real calendar dates only", () => {
    expect(parseIso("2026-11-01")).toEqual({ y: 2026, m: 11, d: 1 });
    expect(parseIso("2024-02-29")).toEqual({ y: 2024, m: 2, d: 29 });
    for (const bad of [
      "2025-02-29",
      "2026-13-01",
      "2026-00-10",
      "2026-04-31",
      "2026-1-1",
      "",
      "x",
      "2026-11-01T00:00",
    ]) {
      expect(parseIso(bad), bad).toBeNull();
    }
  });
});

describe("daysInMonth", () => {
  it("knows leap years, including the century rules", () => {
    expect(daysInMonth(2024, 2)).toBe(29);
    expect(daysInMonth(2025, 2)).toBe(28);
    expect(daysInMonth(1900, 2)).toBe(28);
    expect(daysInMonth(2000, 2)).toBe(29);
    expect(daysInMonth(2026, 11)).toBe(30);
    expect(daysInMonth(2026, 12)).toBe(31);
  });
});

describe("addDays and addMonths", () => {
  it("crosses month and year ends", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(addDays("2024-03-01", -1)).toBe("2024-02-29");
  });

  it("is not thrown by the clocks changing: 29 March 2026 is a 23-hour day", () => {
    expect(addDays("2026-03-28", 1)).toBe("2026-03-29");
    expect(addDays("2026-03-28", 2)).toBe("2026-03-30");
    expect(addDays("2026-10-24", 2)).toBe("2026-10-26");
  });

  it("clamps to the end of a shorter month", () => {
    expect(addMonths("2026-01-31", 1)).toBe("2026-02-28");
    expect(addMonths("2024-01-31", 1)).toBe("2024-02-29");
    expect(addMonths("2026-03-31", -1)).toBe("2026-02-28");
    expect(addMonths("2026-11-15", 3)).toBe("2027-02-15");
    expect(addMonths("2026-11-15", -12)).toBe("2025-11-15");
  });
});

describe("weeks start on Monday (UK)", () => {
  it("numbers days Monday = 0 to Sunday = 6", () => {
    expect(isoWeekdayIndex("2026-11-01")).toBe(6); // a Sunday
    expect(isoWeekdayIndex("2026-11-02")).toBe(0); // a Monday
  });

  it("finds the Monday on or before a date", () => {
    expect(startOfWeek("2026-11-01")).toBe("2026-10-26");
    expect(startOfWeek("2026-11-02")).toBe("2026-11-02");
    expect(startOfWeek("2027-01-01")).toBe("2026-12-28");
  });
});

describe("monthGrid", () => {
  it("is six Monday-first weeks that contain the whole month", () => {
    const grid = monthGrid(2026, 11);
    expect(grid).toHaveLength(6);
    for (const week of grid) expect(week).toHaveLength(7);
    expect(grid[0]?.[0]).toBe("2026-10-26");
    expect(grid[0]?.[6]).toBe("2026-11-01");
    expect(grid.flat()).toContain("2026-11-30");
    expect(grid.flat().at(-1)).toBe("2026-12-06");
  });

  it("has consecutive days with none missing or repeated", () => {
    const days = monthGrid(2024, 2).flat();
    days.forEach((day, i) => {
      if (i > 0) expect(day).toBe(addDays(days[i - 1] ?? "", 1));
    });
  });

  it("starts the week on the 1st when it is a Monday", () => {
    expect(monthGrid(2026, 6)[0]?.[0]).toBe("2026-06-01");
  });
});

describe("formatUk", () => {
  it("writes dates like 1 Nov 2026 (plan 5.8)", () => {
    expect(formatUk("2026-11-01")).toBe("1 Nov 2026");
    expect(formatUk("2026-03-09")).toBe("9 Mar 2026");
    expect(formatUkLong("2026-11-01")).toBe("Sunday 1 November 2026");
  });
});

describe("parseUk", () => {
  it.each([
    ["1 Nov 2026", "2026-11-01"],
    ["01 nov 2026", "2026-11-01"],
    ["1 November 2026", "2026-11-01"],
    ["  1   Nov   2026 ", "2026-11-01"],
    ["1/11/2026", "2026-11-01"],
    ["01/11/2026", "2026-11-01"],
    ["1.11.2026", "2026-11-01"],
    ["1-11-2026", "2026-11-01"],
    ["1/11/26", "2026-11-01"],
    ["2026-11-01", "2026-11-01"],
    ["29 Feb 2024", "2024-02-29"],
    ["5 Sept 2026", "2026-09-05"],
  ])("reads %s as %s", (text, iso) => {
    expect(parseUk(text)).toBe(iso);
  });

  it("reads day/month/year the British way, never month first", () => {
    expect(parseUk("3/4/2026")).toBe("2026-04-03");
    expect(parseUk("12/25/2026")).toBeNull();
  });

  it("treats a two-digit year 70 or more as the 1900s (dates of birth) and below as the 2000s", () => {
    expect(parseUk("1/1/85")).toBe("1985-01-01");
    expect(parseUk("1/1/05")).toBe("2005-01-01");
    expect(parseUk("1/1/69")).toBe("2069-01-01");
    expect(parseUk("1/1/70")).toBe("1970-01-01");
  });

  it.each([
    "",
    "   ",
    "31 Feb 2026",
    "29 Feb 2025",
    "32/1/2026",
    "1/13/2026",
    "Nov 2026",
    "1 Foo 2026",
    "1 Nov",
    "tomorrow",
    "1/11/20266",
    "0/1/2026",
    "1 Nov 0",
  ])("refuses %j instead of guessing", (text) => {
    expect(parseUk(text)).toBeNull();
  });
});

describe("compareIso and todayIso", () => {
  it("orders dates", () => {
    expect(compareIso("2026-01-01", "2026-11-01")).toBeLessThan(0);
    expect(compareIso("2026-11-01", "2026-11-01")).toBe(0);
    expect(compareIso("2027-01-01", "2026-12-31")).toBeGreaterThan(0);
  });

  it("uses the local calendar day, not UTC, so the date does not flip at 00:30 in summer", () => {
    // 00:30 on 1 July in the UK is 23:30 on 30 June UTC; the user's day is 1 July.
    expect(todayIso(new Date(2026, 6, 1, 0, 30))).toBe("2026-07-01");
    expect(todayIso(new Date(2026, 11, 31, 23, 59))).toBe("2026-12-31");
  });
});

describe("formatUkDateTime", () => {
  it("prints UK local time, GMT in winter and BST in summer", () => {
    expect(formatUkDateTime("2026-11-01T09:05:00Z")).toBe("1 Nov 2026, 09:05");
    expect(formatUkDateTime("2026-07-01T08:30:00Z")).toBe("1 Jul 2026, 09:30");
    expect(formatUkDateTime("2026-03-29T00:59:00Z")).toBe("29 Mar 2026, 00:59");
    expect(formatUkDateTime("2026-03-29T01:00:00Z")).toBe("29 Mar 2026, 02:00");
  });

  it("uses the same month names as formatUk", () => {
    expect(formatUkDateTime("2026-09-05T12:00:00Z")).toBe("5 Sep 2026, 13:00");
  });

  it("gives nothing for a value that is not a date", () => {
    expect(formatUkDateTime("not a date")).toBe("");
    expect(formatUkDateTime("")).toBe("");
  });
});

describe("ukDayIso (ISS-20)", () => {
  it("gives the UK calendar day, not the UTC one", () => {
    expect(ukDayIso("2026-07-14T23:30:00Z")).toBe("2026-07-15"); // 00:30 BST
    expect(ukDayIso("2026-01-14T23:30:00Z")).toBe("2026-01-14"); // 23:30 GMT
    expect(ukDayIso("not a date")).toBe("");
  });
});
