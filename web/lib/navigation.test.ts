import { existsSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  MOBILE_TABS,
  NAV_GROUPS,
  NAV_ITEMS,
  breadcrumbsFor,
  findNavItem,
  isActive,
} from "./navigation";

describe("the navigation definition", () => {
  it("has the six groups from the plan, in order (plan 5.6)", () => {
    expect(NAV_GROUPS.map((group) => group.label)).toEqual([
      "Overview",
      "People",
      "Compliance",
      "Time",
      "Me",
      "Company",
    ]);
  });

  it("gives every item a unique id and a unique address", () => {
    expect(new Set(NAV_ITEMS.map((item) => item.id)).size).toBe(NAV_ITEMS.length);
    expect(new Set(NAV_ITEMS.map((item) => item.href)).size).toBe(NAV_ITEMS.length);
  });

  it("uses plain, sentence-case labels and addresses inside the signed-in app", () => {
    for (const item of NAV_ITEMS) {
      expect(item.href, item.id).toMatch(/^\/[a-z][a-z0-9-]*(\/[a-z][a-z0-9-]*)*$/);
      // Sentence case (plan 5.8): the first letter is a capital and the rest are not shouted.
      expect(item.label, item.id).toMatch(/^[A-Z][a-z]+(?: [a-z]+)*$/);
      expect(item.emptyDescription.length, item.id).toBeGreaterThan(30);
      // The header line and the empty-state explanation say different things.
      expect(item.purpose.length, item.id).toBeGreaterThan(10);
      expect(item.purpose, item.id).toMatch(/\.$/);
      expect(item.purpose, item.id).not.toBe(item.emptyDescription);
    }
  });

  it("has a page for every address in it (T1.3: an empty page for every route in the sidebar)", () => {
    for (const item of NAV_ITEMS) {
      const page = path.resolve(import.meta.dirname, "../app/(app)", `.${item.href}`, "page.tsx");
      expect(
        existsSync(page),
        `${item.href} has no page at ${path.relative(process.cwd(), page)}`,
      ).toBe(true);
    }
  });

  it("makes every mobile tab point at a real item", () => {
    expect(MOBILE_TABS.map((tab) => tab.label)).toEqual([
      "Home",
      "People",
      "Compliance",
      "Time",
      "Me",
    ]);
    for (const tab of MOBILE_TABS)
      expect(
        NAV_ITEMS.some((item) => item.href === tab.href),
        tab.label,
      ).toBe(true);
  });
});

describe("which item is current", () => {
  it("matches the page itself", () => {
    expect(findNavItem("/employees")?.id).toBe("employees");
    expect(findNavItem("/company/billing")?.id).toBe("billing");
  });

  it("matches pages beneath an item (a record under its list)", () => {
    expect(findNavItem("/employees/emp-0042")?.id).toBe("employees");
    expect(findNavItem("/leave/requests/9")?.id).toBe("leave");
  });

  it("prefers the most specific item, so a child does not light up its parent", () => {
    expect(findNavItem("/sponsor-compliance")?.id).toBe("compliance");
    expect(findNavItem("/sponsor-compliance/reminders")?.id).toBe("reminders");
    const hub = NAV_ITEMS.find((i) => i.id === "compliance");
    const child = NAV_ITEMS.find((i) => i.id === "reminders");
    expect(hub && isActive(hub, "/sponsor-compliance/reminders")).toBe(false);
    expect(child && isActive(child, "/sponsor-compliance/reminders")).toBe(true);
  });

  it("does not match a different word that only starts the same (/leaves is not /leave)", () => {
    expect(findNavItem("/leaves")).toBeUndefined();
    expect(findNavItem("/employeesx")).toBeUndefined();
  });

  it("knows nothing about unknown pages and ignores a trailing slash, query and hash", () => {
    expect(findNavItem("/nonsense")).toBeUndefined();
    expect(findNavItem("/employees/")?.id).toBe("employees");
    expect(findNavItem("/employees?x=1#top")?.id).toBe("employees");
  });
});

describe("breadcrumbs", () => {
  it("name the group, then the page (plan 5.6)", () => {
    expect(breadcrumbsFor("/employees").map((c) => c.label)).toEqual(["People", "Employees"]);
  });

  it("add the parent page when there is one", () => {
    expect(breadcrumbsFor("/sponsor-compliance/migrant-employees").map((c) => c.label)).toEqual([
      "Compliance",
      "Sponsor compliance",
      "Sponsored employees",
    ]);
  });

  it("only the last one is the current page, and the group is not a link", () => {
    const crumbs = breadcrumbsFor("/sponsor-compliance/reminders");
    expect(crumbs.at(-1)?.href).toBeUndefined();
    expect(crumbs[0]?.href).toBeUndefined();
    expect(crumbs[1]?.href).toBe("/sponsor-compliance");
  });

  it("are empty for a page the navigation does not know", () => {
    expect(breadcrumbsFor("/nonsense")).toEqual([]);
  });
});

describe("the company set-up pages", () => {
  it("sit under Company in the breadcrumbs and have their own heading", async () => {
    const { breadcrumbsFor, titleFor } = await import("./navigation");
    expect(breadcrumbsFor("/company/locations")).toEqual([
      { label: "Company" },
      { label: "Company", href: "/company" },
      { label: "Locations" },
    ]);
    expect(titleFor("/company/designations")).toBe("Designations");
    expect(titleFor("/company")).toBe("Company");
    expect(titleFor("/company/pay-bands")).toBe("Pay bands");
    expect(titleFor("/company/delete-account")).toBe("Delete company account");
  });
});
