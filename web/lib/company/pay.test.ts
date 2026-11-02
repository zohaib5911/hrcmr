import { describe, expect, it } from "vitest";

import { bandRange, formatMoney, percent, scheduleSummary } from "./pay";

describe("pay settings wording", () => {
  it("formats money and ranges", () => {
    expect(formatMoney("28000.00")).toBe("£28,000");
    expect(formatMoney(1500, "EUR")).toBe("€1,500");
    expect(bandRange("28000", "34000", "GBP")).toBe("£28,000 to £34,000 a year");
  });
  it("describes a pay day", () => {
    expect(scheduleSummary("weekly", "weekday", 5)).toBe("Weekly, on Fridays");
    expect(scheduleSummary("monthly", "day_of_month", 22)).toBe("Monthly, on the 22nd");
    expect(scheduleSummary("monthly", "day_of_month", 11)).toBe("Monthly, on the 11th");
    expect(scheduleSummary("monthly", "last_working_day", null)).toBe(
      "Monthly, on the last working day",
    );
    expect(scheduleSummary("fortnightly", "weekday", 4)).toBe("Every two weeks, on Thursdays");
  });
  it("shows a percentage without trailing zeros", () => {
    expect(percent("20.00")).toBe("20%");
    expect(percent("19.50")).toBe("19.5%");
  });
});
