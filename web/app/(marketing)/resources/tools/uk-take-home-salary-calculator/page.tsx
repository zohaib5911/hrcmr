import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { UkTakeHomeSalaryCalculator } from "@/components/calculators/uk-take-home-salary-calculator";
import { takeHomeSources } from "@/lib/calculators/uk-take-home-salary-calculator";

export const metadata: Metadata = {
  title: "UK take-home salary calculator",
  description:
    "Estimate annual, monthly and weekly take-home pay for England, Scotland and Wales after tax, National Insurance, pension and student loans.",
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="UK take-home salary calculator"
      description="Estimate take-home pay for 2026 to 2027 after income tax, National Insurance, pension and student loans, with a breakdown."
      sources={takeHomeSources}
    >
      <UkTakeHomeSalaryCalculator />
    </CalculatorTemplate>
  );
}
