import { describe, expect, it } from "vitest";

import {
  MAX_RECENT,
  RECENT_PAGES_KEY,
  parseRecent,
  pushRecent,
  serialiseRecent,
} from "./recent-pages";

const KNOWN = [
  "/dashboard",
  "/employees",
  "/leave",
  "/rota",
  "/reports",
  "/policies",
  "/documents",
  "/profile",
  "/work-log",
  "/learning",
];

describe("recent pages (plan 8.19: stored in localStorage, at most 8)", () => {
  it("is stored under the name from the plan", () => {
    expect(RECENT_PAGES_KEY).toBe("brand.recentPages");
    expect(MAX_RECENT).toBe(8);
  });

  it("puts the newest first and moves a revisited page to the front instead of repeating it", () => {
    let list: string[] = [];
    for (const href of ["/leave", "/employees", "/leave"]) list = pushRecent(list, href);
    expect(list).toEqual(["/leave", "/employees"]);
  });

  it("keeps only the eight most recent", () => {
    let list: string[] = [];
    for (const href of KNOWN) list = pushRecent(list, href);
    expect(list).toHaveLength(8);
    expect(list[0]).toBe("/learning");
    expect(list).not.toContain("/dashboard");
  });

  it("does not change the list it was given", () => {
    const before = ["/leave"];
    pushRecent(before, "/rota");
    expect(before).toEqual(["/leave"]);
  });
});

describe("reading the stored list back", () => {
  it("reads what was written", () => {
    expect(parseRecent(serialiseRecent(["/leave", "/rota"]), KNOWN)).toEqual(["/leave", "/rota"]);
  });

  it("is empty when nothing is stored or the store is unreadable", () => {
    expect(parseRecent(null, KNOWN)).toEqual([]);
    expect(parseRecent("", KNOWN)).toEqual([]);
    expect(parseRecent("not json {", KNOWN)).toEqual([]);
    expect(parseRecent('{"a":1}', KNOWN)).toEqual([]);
    expect(parseRecent("42", KNOWN)).toEqual([]);
  });

  it("drops anything that is not a page of the app: localStorage is not trusted", () => {
    const stored = JSON.stringify([
      "/leave",
      "javascript:alert(1)",
      "https://evil.example/phish",
      "//evil.example",
      7,
      null,
      "/rota",
      "/employees/../../etc",
    ]);
    expect(parseRecent(stored, KNOWN)).toEqual(["/leave", "/rota"]);
  });

  it("drops repeats and caps the length even if someone edited the store", () => {
    const stored = JSON.stringify([...KNOWN, ...KNOWN]);
    const list = parseRecent(stored, KNOWN);
    expect(list).toHaveLength(8);
    expect(new Set(list).size).toBe(8);
  });
});
