import { describe, expect, it } from "vitest";

import { clamp, formatNumber, parseDecimal, stepValue } from "./numbers";

describe("parseDecimal", () => {
  it.each([
    ["41700", 41700],
    ["41,700", 41700],
    ["£41,700", 41700],
    ["£ 41,700.50", 41700.5],
    ["  7.5 ", 7.5],
    ["-3", -3],
    ["0", 0],
    [".5", 0.5],
    ["12h", 12],
    ["1,234,567.89", 1234567.89],
  ])("reads %j as %d", (text, value) => {
    expect(parseDecimal(text)).toBe(value);
  });

  it.each([
    "",
    "  ",
    "abc",
    "1.2.3",
    "1,2,3",
    "--5",
    "5-",
    "1e5",
    "£",
    "NaN",
    "Infinity",
    "1,23.4,5",
  ])("refuses %j", (text) => {
    expect(parseDecimal(text)).toBeNull();
  });
});

describe("formatNumber", () => {
  it("groups thousands the British way and fixes decimal places", () => {
    expect(formatNumber(41700, 0)).toBe("41,700");
    expect(formatNumber(41700.5, 2)).toBe("41,700.50");
    expect(formatNumber(7.5, 1)).toBe("7.5");
    expect(formatNumber(0, 2)).toBe("0.00");
    expect(formatNumber(-1234.5, 2)).toBe("-1,234.50");
  });
});

describe("clamp and stepValue", () => {
  it("clamps to optional bounds", () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-1, 0, 10)).toBe(0);
    expect(clamp(11, 0, 10)).toBe(10);
    expect(clamp(11, undefined, undefined)).toBe(11);
  });

  it("steps without floating point drift: 0.1 + 0.2 is 0.3", () => {
    expect(stepValue(0.1, 0.1, 1, { decimals: 1 })).toBe(0.2);
    expect(stepValue(0.2, 0.1, 1, { decimals: 1 })).toBe(0.3);
    expect(stepValue(10, 0.5, -1, { decimals: 2, min: 0 })).toBe(9.5);
  });

  it("stays inside the bounds and starts from zero when empty", () => {
    expect(stepValue(null, 1, 1, { decimals: 0 })).toBe(1);
    expect(stepValue(0, 1, -1, { decimals: 0, min: 0 })).toBe(0);
    expect(stepValue(9.5, 1, 1, { decimals: 1, max: 10 })).toBe(10);
  });
});
