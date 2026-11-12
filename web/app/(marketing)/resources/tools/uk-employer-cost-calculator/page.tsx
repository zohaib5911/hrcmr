import type { Metadata } from "next";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { EmployerCostCalculator } from "@/components/calculators/uk-employer-cost-calculator";
import { employerCostSources } from "@/lib/calculators/uk-employer-cost-calculator";

export const metadata: Metadata = {
  title: "UK employer cost calculator",
  description:
    "Estimate annual UK employer National Insurance, pension contributions and total salary cost, with an Apprenticeship Levy note.",
};
export default function Page() {
  return (
    <CalculatorTemplate
      title="UK employer cost calculator"
      description="Estimate annual salary, employer National Insurance and pension costs for an employee or recognised apprentice."
      sources={employerCostSources}
    >
      <EmployerCostCalculator />
    </CalculatorTemplate>
  );
}
