import { describe, expect, it } from "vitest";

import { compareValues, sortRows } from "./sort";

const by = <T extends { v: string | number | null }>(rows: T[], direction: "asc" | "desc") =>
  sortRows(rows, (row) => row.v, direction).map((row) => row.v);

describe("compareValues", () => {
  it("orders numbers numerically, not as text", () => {
    expect(compareValues(2, 10)).toBeLessThan(0);
    expect(compareValues(10, 2)).toBeGreaterThan(0);
    expect(compareValues(5, 5)).toBe(0);
  });

  it("orders text without caring about case or accents, and numbers inside text naturally", () => {
    expect(compareValues("apple", "Banana")).toBeLessThan(0);
    expect(compareValues("Zoë", "zoe")).toBe(0);
    expect(compareValues("Employee 2", "Employee 10")).toBeLessThan(0);
  });

  it("puts numbers before text when a column mixes them", () => {
    expect(compareValues(3, "a")).toBeLessThan(0);
    expect(compareValues("a", 3)).toBeGreaterThan(0);
  });
});

describe("sortRows", () => {
  it("sorts ascending and descending", () => {
    const rows = [{ v: 3 }, { v: 1 }, { v: 2 }];
    expect(by(rows, "asc")).toEqual([1, 2, 3]);
    expect(by(rows, "desc")).toEqual([3, 2, 1]);
  });

  it("keeps empty cells at the bottom in both directions", () => {
    const rows = [{ v: null }, { v: "b" }, { v: "a" }, { v: null }];
    expect(by(rows, "asc")).toEqual(["a", "b", null, null]);
    expect(by(rows, "desc")).toEqual(["b", "a", null, null]);
  });

  it("is stable: equal rows keep their order, so re-sorting never shuffles them", () => {
    const rows = [
      { v: 1, id: "a" },
      { v: 1, id: "b" },
      { v: 0, id: "c" },
      { v: 1, id: "d" },
    ];
    expect(sortRows(rows, (r) => r.v, "asc").map((r) => r.id)).toEqual(["c", "a", "b", "d"]);
    expect(sortRows(rows, (r) => r.v, "desc").map((r) => r.id)).toEqual(["a", "b", "d", "c"]);
  });

  it("does not change the list it was given", () => {
    const rows = [{ v: 2 }, { v: 1 }];
    sortRows(rows, (r) => r.v, "asc");
    expect(rows.map((r) => r.v)).toEqual([2, 1]);
  });
});
