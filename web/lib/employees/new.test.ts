import { describe, expect, it } from "vitest";

import { EMPTY_EMPLOYEE, latestHireDate, newEmployeeProblems } from "./new";

const good = {
  ...EMPTY_EMPLOYEE,
  firstName: "Amira",
  lastName: "Hassan",
  email: "amira@example.com",
  employeeNumber: "E001",
  hireDate: "2026-12-01",
};

describe("latestHireDate", () => {
  it("is a year away, and 28 February for a leap day", () => {
    expect(latestHireDate("2026-11-02")).toBe("2027-11-02");
    expect(latestHireDate("2028-02-29")).toBe("2029-02-28");
  });
});

describe("newEmployeeProblems", () => {
  it("accepts the essentials", () => {
    expect(newEmployeeProblems(good, "2026-11-02")).toEqual({});
  });

  it("names each missing or wrong field", () => {
    const found = newEmployeeProblems(EMPTY_EMPLOYEE, "2026-11-02");
    expect(Object.keys(found).sort()).toEqual(
      ["email", "employee_number", "first_name", "hire_date", "last_name"].sort(),
    );
    expect(newEmployeeProblems({ ...good, email: "nope" }, "2026-11-02").email).toBeDefined();
  });

  it("refuses a hire date more than 12 months ahead, but allows exactly 12", () => {
    expect(
      newEmployeeProblems({ ...good, hireDate: "2027-11-03" }, "2026-11-02").hire_date,
    ).toMatch(/12 months/);
    expect(newEmployeeProblems({ ...good, hireDate: "2027-11-02" }, "2026-11-02")).toEqual({});
  });
});
