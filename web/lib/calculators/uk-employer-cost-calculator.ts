import payroll2025 from "@/rates/payroll-2025-26.json";
import payroll2026 from "@/rates/payroll-2026-27.json";
import pension from "@/rates/pension.json";

export const employerCostYears = {
  "2026-2027": payroll2026,
  "2025-2026": payroll2025,
} as const;
export type EmployerCostInput = {
  taxYear: keyof typeof employerCostYears;
  salary: number;
  age: number;
  employeeType: "standard" | "apprentice";
  pensionRate: number; // Percentage, e.g. 3, chosen by the employer.
  pensionBasis: "qualifying" | "full";
};
export const defaultEmployerPensionRate = pension.values.minimum_employer_rate * 100;
export const employerCostSources = [payroll2026, payroll2025, pension].map((source) => ({
  title: source.title,
  url: source.source_url,
  checkedOn: source.checked_on,
  validFrom: source.valid_from,
  validTo: source.valid_to,
}));
const money = (amount: number) => Math.round((amount + Number.EPSILON) * 100) / 100;

/** Annual budget estimate for a full year at unchanged salary, age and NI status. */
export function calculateEmployerCost(input: EmployerCostInput) {
  if (
    !Object.hasOwn(employerCostYears, input.taxYear) ||
    !Number.isFinite(input.salary) ||
    input.salary < 0 ||
    !Number.isInteger(input.age) ||
    input.age < 0 ||
    !Number.isFinite(input.pensionRate) ||
    input.pensionRate < 0 ||
    input.pensionRate > 100 ||
    !["standard", "apprentice"].includes(input.employeeType) ||
    !["qualifying", "full"].includes(input.pensionBasis)
  )
    throw new Error(
      "Check the tax year, salary, whole-year age, employee type and pension percentage (0–100).",
    );

  const rates = employerCostYears[input.taxYear].values;
  const category =
    input.employeeType === "apprentice" && input.age < rates.employer_ni_apprentice_under_age
      ? "H"
      : input.age < rates.employer_ni_under_age
        ? "M"
        : "A";
  const thresholds = rates.ni_thresholds;
  const niThreshold =
    category === "H"
      ? thresholds["Apprentice upper secondary threshold (apprentice under 25)"].year
      : category === "M"
        ? thresholds["Upper secondary threshold (under 21)"].year
        : thresholds["Secondary threshold"].year;
  const niRate = rates.employer_ni_rates[category][3];
  const niEarnings = money(Math.max(0, input.salary - niThreshold));
  const employerNI = money(niEarnings * niRate);
  const pensionableEarnings = money(
    input.pensionBasis === "full"
      ? input.salary
      : Math.max(
          0,
          Math.min(input.salary, pension.values.qualifying_earnings_upper_annual) -
            pension.values.qualifying_earnings_lower_annual,
        ),
  );
  const employerPension = money((pensionableEarnings * input.pensionRate) / 100);
  const totalCost = money(input.salary + employerNI + employerPension);
  if (
    ![niEarnings, employerNI, pensionableEarnings, employerPension, totalCost].every(
      Number.isFinite,
    )
  ) {
    throw new Error("Enter a smaller salary.");
  }
  return {
    category,
    niThreshold,
    niRate,
    niEarnings,
    employerNI,
    pensionableEarnings,
    employerPension,
    totalCost,
    levyRate: rates.apprenticeship_levy_rate,
    levyAllowance: rates.apprenticeship_levy_allowance_annual,
    levyPayBillThreshold: rates.apprenticeship_levy_pay_bill_threshold,
  };
}
