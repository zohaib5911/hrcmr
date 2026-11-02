import { describe, expect, it } from "vitest";

import {
  ALL_DEPARTMENTS,
  departmentsIn,
  filterEmployees,
  pillFromParam,
  summaryLine,
  type EmployeeRow,
} from "./list";

const row = (over: Partial<EmployeeRow>): EmployeeRow => ({
  id: "1",
  employee_number: "E 001",
  first_name: "Amira",
  last_name: "Hassan",
  email: "amira@example.com",
  status: "active",
  hire_date: "2025-01-06",
  department_id: null,
  department: "Care",
  designation: null,
  has_photo: false,
  ...over,
});

const rows = [
  row({}),
  row({
    id: "2",
    employee_number: "E002",
    first_name: "Ben",
    last_name: "Okafor",
    status: "on_leave",
    department: "Kitchen",
  }),
  row({
    id: "3",
    employee_number: "E003",
    first_name: "Cleo",
    last_name: "Ng",
    status: "leaver",
    department: null,
  }),
];
const none = { pill: "all", department: ALL_DEPARTMENTS, search: "" } as const;

describe("filterEmployees", () => {
  it("filters by pill and department", () => {
    expect(filterEmployees(rows, none)).toHaveLength(3);
    expect(filterEmployees(rows, { ...none, pill: "on_leave" }).map((r) => r.id)).toEqual(["2"]);
    expect(filterEmployees(rows, { ...none, department: "Care" }).map((r) => r.id)).toEqual(["1"]);
  });

  it("searches names and numbers, ignoring case and spaces", () => {
    expect(filterEmployees(rows, { ...none, search: "ben OKAFOR" })).toHaveLength(1);
    expect(filterEmployees(rows, { ...none, search: "e001" })).toHaveLength(1);
    expect(filterEmployees(rows, { ...none, search: "zzz" })).toHaveLength(0);
  });
});

describe("pills, summary and departments", () => {
  it("reads a deep link, defaulting to All", () => {
    expect(pillFromParam("leaver")).toBe("leaver");
    expect(pillFromParam(["active", "x"])).toBe("active");
    expect(pillFromParam("nonsense")).toBe("all");
    expect(pillFromParam(undefined)).toBe("all");
  });

  it("words the summary and leaves out zeros", () => {
    expect(summaryLine({ total: 12, active: 10, on_leave: 1, leavers: 1, archived: 4 })).toBe(
      "12 employees · 10 active · 1 on leave · 1 leaver",
    );
    expect(summaryLine({ total: 1, active: 1, on_leave: 0, leavers: 0, archived: 0 })).toBe(
      "1 employee · 1 active",
    );
  });

  it("lists each department once, sorted", () => {
    expect(departmentsIn(rows)).toEqual(["Care", "Kitchen"]);
  });
});
