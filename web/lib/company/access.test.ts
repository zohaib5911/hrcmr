import { describe, expect, it } from "vitest";

import {
  filterUsers,
  fullName,
  NO_FILTERS,
  rowActions,
  unlinkedBanner,
  type AccessUser,
} from "./access";

const user = (over: Partial<AccessUser>): AccessUser => ({
  id: "m1",
  user_id: "u1",
  first_name: "Amira",
  last_name: "Hassan",
  email: "amira@example.com",
  role: "company_admin",
  status: "active",
  two_step: true,
  employee_id: null,
  last_login_at: null,
  invite_expires_at: null,
  is_you: false,
  ...over,
});

const people = [
  user({}),
  user({ id: "m2", first_name: "Ben", last_name: "Okafor", email: "ben@x.com", role: "employee" }),
  user({ id: "m3", first_name: "Cleo", last_name: "Ng", role: "employee", status: "suspended" }),
];

describe("filterUsers", () => {
  it("keeps everyone with no filters", () => {
    expect(filterUsers(people, NO_FILTERS)).toHaveLength(3);
  });

  it("filters by role, by status and by both", () => {
    expect(filterUsers(people, { ...NO_FILTERS, role: "employee" })).toHaveLength(2);
    expect(filterUsers(people, { ...NO_FILTERS, status: "suspended" })).toHaveLength(1);
    expect(filterUsers(people, { role: "employee", status: "active", search: "" })).toHaveLength(1);
  });

  it("searches name and e-mail, every word, ignoring case", () => {
    expect(filterUsers(people, { ...NO_FILTERS, search: "ben OKAFOR" })).toHaveLength(1);
    expect(filterUsers(people, { ...NO_FILTERS, search: "ben@x" })).toHaveLength(1);
    expect(filterUsers(people, { ...NO_FILTERS, search: "ben hassan" })).toHaveLength(0);
  });
});

describe("unlinkedBanner and fullName", () => {
  it("words the count, and hides at zero", () => {
    expect(unlinkedBanner(0)).toBeNull();
    expect(unlinkedBanner(1)).toBe("1 unlinked user");
    expect(unlinkedBanner(4)).toBe("4 unlinked users");
  });

  it("joins the names", () => {
    expect(fullName(people[0]!)).toBe("Amira Hassan");
  });
});

describe("rowActions", () => {
  const admin = { role: "company_admin", canInvite: true, canAssign: true };
  const hr = { role: "hr_admin", canInvite: true, canAssign: false };

  it("offers a member's role, suspend and, with two-step on, reset", () => {
    expect(rowActions(user({ role: "employee", two_step: false }), admin)).toEqual([
      "role",
      "suspend",
    ]);
    expect(rowActions(user({ role: "employee", two_step: true }), admin)).toEqual([
      "role",
      "suspend",
      "reset",
    ]);
    expect(rowActions(people[2]!, admin)).toEqual(["role", "reactivate", "reset"]);
  });

  it("offers nothing on yourself, on an admin to a non-admin, or without the permission", () => {
    expect(rowActions(user({ is_you: true }), admin)).toEqual([]);
    expect(rowActions(people[1]!, hr)).toEqual([]);
    expect(rowActions(user({}), { ...admin, role: "hr_admin" })).toEqual([]);
  });

  it("offers resend and cancel on an invitation, to someone who may invite", () => {
    const invited = user({ status: "invited", role: "recruiter" });
    expect(rowActions(invited, hr)).toEqual(["resend", "cancel"]);
    expect(rowActions({ ...invited, role: "company_admin" }, hr)).toEqual([]);
    expect(rowActions(invited, { ...hr, canInvite: false })).toEqual([]);
  });
});
