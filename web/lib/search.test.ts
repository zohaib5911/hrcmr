import { describe, expect, it } from "vitest";

import { normalise, rankPages } from "./search";

const ITEMS = [
  { id: "dashboard", label: "Dashboard", group: "Overview", href: "/dashboard" },
  { id: "employees", label: "Employees", group: "People", href: "/employees" },
  {
    id: "compliance",
    label: "Sponsor compliance",
    group: "Compliance",
    href: "/sponsor-compliance",
  },
  {
    id: "migrant",
    label: "Sponsored employees",
    group: "Compliance",
    href: "/sponsor-compliance/migrant-employees",
  },
  {
    id: "reminders",
    label: "Reminders",
    group: "Compliance",
    href: "/sponsor-compliance/reminders",
  },
  { id: "leave", label: "Leave", group: "Time", href: "/leave" },
  { id: "profile", label: "My profile", group: "Me", href: "/profile" },
  { id: "documents", label: "Documents", group: "Compliance", href: "/documents" },
  { id: "my-documents", label: "My documents", group: "Me", href: "/my-documents" },
];

const ids = (query: string) => rankPages(query, ITEMS).map((item) => item.id);

describe("normalise", () => {
  it("ignores case, accents and spacing", () => {
    expect(normalise("  Café  Zoë ")).toBe("cafe zoe");
    expect(normalise("ŁUKASZ")).toBe(
      "łukasz".normalize("NFD").replace(/\p{M}/gu, "").toLowerCase(),
    );
  });
});

describe("rankPages", () => {
  it("shows everything, in the order given, for an empty search", () => {
    expect(ids("")).toEqual(ITEMS.map((i) => i.id));
    expect(ids("   ")).toEqual(ITEMS.map((i) => i.id));
  });

  it("finds a page by the start of its name, whatever the case", () => {
    expect(ids("emp")[0]).toBe("employees");
    expect(ids("DASH")).toEqual(["dashboard"]);
  });

  it("puts a name that STARTS with the search before one that merely contains it", () => {
    expect(ids("document")).toEqual(["documents", "my-documents"]);
    expect(ids("leave")[0]).toBe("leave");
  });

  it("matches the start of any word in a name", () => {
    expect(ids("compliance")).toContain("compliance");
    expect(ids("profile")).toEqual(["profile"]);
  });

  it("matches the group a page is in", () => {
    expect(ids("time")).toEqual(["leave"]);
    expect(ids("overview")).toEqual(["dashboard"]);
  });

  it("needs every word to match something", () => {
    expect(ids("sponsor employees")).toEqual(["migrant"]);
    expect(ids("sponsor xyz")).toEqual([]);
  });

  it("finds nothing for nonsense, and does not treat characters as a pattern", () => {
    expect(ids("zzz")).toEqual([]);
    expect(ids(".*")).toEqual([]);
    expect(ids("(")).toEqual([]);
  });

  it("is not thrown by accents", () => {
    expect(ids("rémindérs")).toEqual(["reminders"]);
  });

  it("does not change the list it was given", () => {
    const copy = [...ITEMS];
    rankPages("emp", ITEMS);
    expect(ITEMS).toEqual(copy);
  });
});
