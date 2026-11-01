import { describe, expect, it } from "vitest";

import { formatTime, parseTime, stepTime } from "./time";

describe("parseTime", () => {
  it.each([
    ["09:30", "09:30"],
    ["9:30", "09:30"],
    ["930", "09:30"],
    ["0930", "09:30"],
    ["9.30", "09:30"],
    ["9", "09:00"],
    ["09", "09:00"],
    ["17", "17:00"],
    ["0", "00:00"],
    ["23:59", "23:59"],
    ["9:30am", "09:30"],
    ["9:30 PM", "21:30"],
    ["12am", "00:00"],
    ["12pm", "12:00"],
    ["12:15 am", "00:15"],
    ["5pm", "17:00"],
  ])("reads %j as %s", (text, value) => {
    expect(parseTime(text)).toBe(value);
  });

  it.each(["", "24:00", "9:60", "25", "9:5x", "abc", "13pm", "0pm", "9:30:15", "-1", "1230pm5"])(
    "refuses %j",
    (text) => {
      expect(parseTime(text)).toBeNull();
    },
  );
});

describe("stepTime", () => {
  it("moves by the step and stays inside the day", () => {
    expect(stepTime("09:00", 15, 1)).toBe("09:15");
    expect(stepTime("09:50", 15, 1)).toBe("10:05");
    expect(stepTime("00:05", 15, -1)).toBe("00:00");
    expect(stepTime("23:55", 15, 1)).toBe("23:59");
  });

  it("starts at a sensible time when empty", () => {
    expect(stepTime(null, 15, 1)).toBe("09:00");
    expect(stepTime(null, 15, -1)).toBe("09:00");
  });
});

describe("formatTime", () => {
  it("is 24-hour with two digits (plan 5.8)", () => {
    expect(formatTime(9, 5)).toBe("09:05");
    expect(formatTime(0, 0)).toBe("00:00");
  });
});
