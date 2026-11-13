import { describe, expect, it } from "vitest";

import { routeSkeleton } from "./route-skeleton";

describe("routeSkeleton", () => {
  it.each([
    ["/dashboard", "card"],
    ["/reports", "card"],
    ["/sponsor-compliance", "card"],
    ["/employees/7f1c", "card"],
    ["/rota", "calendar"],
    ["/my-shifts", "calendar"],
    ["/holiday-management", "calendar"],
    ["/rota/settings", "form"],
    ["/company/departments", "form"],
    ["/profile", "form"],
    ["/employees/new", "form"],
    ["/employees", "list"],
    ["/employees/archived", "list"],
    ["/sponsor-compliance/reminders", "list"],
    ["/documents/", "list"],
    ["/recruitment?stage=offer", "list"],
  ] as const)("%s shows the %s skeleton", (path, family) => {
    expect(routeSkeleton(path)).toBe(family);
  });
});
