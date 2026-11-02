export interface NewEmployee {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  employeeNumber: string;
  hireDate: string | null;
  status: "active" | "on_leave";
}

export const EMPTY_EMPLOYEE: NewEmployee = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  employeeNumber: "",
  hireDate: null,
  status: "active",
};

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** The latest hire date allowed: 12 months from today (29 February becomes 28 February). */
export function latestHireDate(today: string): string {
  const [year = "", month = "", day = ""] = today.split("-");
  const next = Number(year) + 1;
  const isLeapDay = month === "02" && day === "29";
  return `${next}-${month}-${isLeapDay ? "28" : day}`;
}

/** A message per field that cannot be sent as it is; empty when everything is fine. */
export function newEmployeeProblems(values: NewEmployee, today: string): Record<string, string> {
  const found: Record<string, string> = {};
  if (!values.firstName.trim()) found.first_name = "Enter their first name.";
  if (!values.lastName.trim()) found.last_name = "Enter their last name.";
  if (!EMAIL.test(values.email.trim()))
    found.email = "Enter an email address, like name@company.com.";
  if (!values.employeeNumber.trim()) found.employee_number = "Enter an employee number.";
  if (!values.hireDate) found.hire_date = "Choose the hire date.";
  else if (values.hireDate > latestHireDate(today)) {
    found.hire_date = "The hire date can be at most 12 months from today.";
  }
  return found;
}
