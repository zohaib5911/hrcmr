import { describe, expect, it } from "vitest";
import { rtwFilterFromParam } from "./rtw";

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
  rtw_status: "not_recorded",
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
    expect(
      summaryLine({
        total: 12,
        active: 10,
        on_leave: 1,
        leavers: 1,
        archived: 4,
        rtw_needs_attention: 2,
        rtw_verified: 10,
      }),
    ).toBe("12 employees · 10 active · 1 on leave · 1 leaver · 2 need Right to Work action");
    expect(
      summaryLine({
        total: 1,
        active: 1,
        on_leave: 0,
        leavers: 0,
        archived: 0,
        rtw_needs_attention: 0,
        rtw_verified: 1,
      }),
    ).toBe("1 employee · 1 active · all Right to Work checks current");
  });

  it("lists each department once, sorted", () => {
    expect(departmentsIn(rows)).toEqual(["Care", "Kitchen"]);
  });
});

it("combines Right to Work attention, status deep links and employee filters", () => {
  const checks = [
    row({ id: "v", rtw_status: "verified" }),
    row({ id: "f", rtw_status: "failed" }),
    row({ id: "e", rtw_status: "expired" }),
    row({ id: "m", rtw_status: "evidence_missing" }),
  ];
  expect(filterEmployees(checks, { ...none, pill: "needs_rtw" }).map((r) => r.id)).toEqual([
    "f",
    "e",
    "m",
  ]);
  expect(filterEmployees(checks, { ...none, rtw: "Expired" }).map((r) => r.id)).toEqual(["f", "e"]);
  expect(
    filterEmployees(checks, { ...none, pill: "active", rtw: "EvidenceMissing" }).map((r) => r.id),
  ).toEqual(["m"]);
  expect(rtwFilterFromParam(["EvidenceMissing", "Verified"])).toBe("EvidenceMissing");
  expect(rtwFilterFromParam("unknown")).toBe("all");
});
