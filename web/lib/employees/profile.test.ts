import { describe, expect, it } from "vitest";

import { joinedLine, MOVES, relative, shortDate } from "./profile";

describe("the profile's dates", () => {
  it("writes dates out and says how long ago", () => {
    expect(shortDate("2026-11-02")).toBe("2 Nov 2026");
    const today = "2026-11-02";
    expect(relative("2026-11-02", today)).toBe("today");
    expect(relative("2026-11-01", today)).toBe("1 day ago");
    expect(relative("2026-10-12", today)).toBe("3 weeks ago");
    expect(relative("2026-06-02", today)).toBe("5 months ago");
    expect(relative("2023-11-02", today)).toBe("3 years ago");
    expect(relative("2026-11-14", today)).toBe("in 12 days");
    expect(joinedLine("2026-11-02", today)).toBe("Joined 2 Nov 2026 · today");
    expect(joinedLine("2026-12-01", today)).toBe("Joins 1 Dec 2026 · in 4 weeks");
  });

  it("offers only the moves that make sense from each state", () => {
    expect(MOVES.archived.map((m) => m.to)).toEqual(["active"]);
    expect(MOVES.active.map((m) => m.to)).toEqual(["on_leave", "leaver", "archived"]);
    for (const [from, moves] of Object.entries(MOVES)) {
      expect(moves.map((m) => m.to)).not.toContain(from);
    }
  });
});
