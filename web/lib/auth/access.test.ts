import { describe, expect, it } from "vitest";

import { NAV_ITEMS } from "@/lib/navigation";

import { NAV_PERMISSIONS, can, visibleGroups } from "./access";
import { isWriteScreen, toShellSession } from "./shell-session";

const ids = (permissions: readonly string[] | null) =>
  visibleGroups(permissions).flatMap((group) => group.items.map((item) => item.id));

describe("the permission-aware navigation", () => {
  it("only lists pages that exist", () => {
    for (const id of Object.keys(NAV_PERMISSIONS)) {
      expect(
        NAV_ITEMS.map((item) => item.id),
        id,
      ).toContain(id);
    }
  });

  it("shows everything until the permissions are known", () => {
    expect(ids(null)).toHaveLength(NAV_ITEMS.length);
  });

  it("shows an employee their own pages, and not the company's people or billing", () => {
    const shown = ids([
      "leave.request.read_own",
      "document.file.read_own",
      "work_log.entry.read_own",
      "employee.profile.read_own",
    ]);
    expect(shown).toEqual(
      expect.arrayContaining(["dashboard", "leave", "my-documents", "my-work-log", "profile"]),
    );
    expect(shown).not.toContain("employees");
    expect(shown).not.toContain("billing");
    expect(shown).not.toContain("users");
  });

  it("drops a group once none of its pages are left, and can() means any of", () => {
    const groups = visibleGroups(["billing.manage"]).map((group) => group.id);
    expect(groups).toEqual(["overview", "me", "company"]);
    expect(can(["a", "b"], "c", "b")).toBe(true);
    expect(can([], "c")).toBe(false);
  });
});

describe("the shell session", () => {
  const me = {
    user: { first_name: "Amira", last_name: "Hassan", email: "amira@example.com" },
    companies: [
      {
        company_id: "c1",
        company_name: "Harbourside Care Ltd",
        plan: "free",
        role: "company_admin",
        status: "active",
      },
      {
        company_id: "c2",
        company_name: "Old Co",
        plan: "ten_year",
        role: "employee",
        status: "suspended",
      },
    ],
    active_company_id: "c1",
    role: "company_admin",
  } as never;

  it("names the person, role and plan, and offers only active companies", () => {
    const session = toShellSession(me);
    expect(session?.user).toEqual({
      name: "Amira Hassan",
      email: "amira@example.com",
      role: "Company Admin",
    });
    expect(session?.company).toEqual({ id: "c1", name: "Harbourside Care Ltd", plan: "free" });
    expect(session?.companies.map((c) => c.id)).toEqual(["c1"]);
  });

  it("has no session until a company is chosen", () => {
    expect(toShellSession({ ...(me as object), active_company_id: null } as never)).toBeNull();
  });

  it("knows the screens where something is being filled in", () => {
    expect(isWriteScreen("/employees/new")).toBe(true);
    expect(isWriteScreen("/employees/abc/edit")).toBe(true);
    expect(isWriteScreen("/employees")).toBe(false);
  });
});
