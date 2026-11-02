import { describe, expect, it } from "vitest";

import { dayRange, longDate } from "./holidays";

describe("holiday dates", () => {
  it("writes a date out with its weekday", () => {
    expect(longDate("2026-01-01")).toBe("Thu 1 Jan 2026");
  });

  it("writes a closure as a range, with the year once when it is the same", () => {
    expect(dayRange("2026-05-01", "2026-05-01")).toBe("1 May 2026");
    expect(dayRange("2026-08-03", "2026-08-14")).toBe("3 Aug to 14 Aug 2026");
    expect(dayRange("2026-12-24", "2027-01-02")).toBe("24 Dec 2026 to 2 Jan 2027");
  });
});
