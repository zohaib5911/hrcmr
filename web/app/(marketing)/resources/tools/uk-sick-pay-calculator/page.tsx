import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SickPayCalculator } from "@/components/calculators/uk-sick-pay-calculator";
import { sickPaySources } from "@/lib/calculators/uk-sick-pay-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/uk-sick-pay-calculator",
  "UK sick pay calculator",
  "Estimate Statutory Sick Pay for an absence, with a week-by-week table, under the rules from 6 April 2026.",
);
export default function Page() {
  return (
    <CalculatorTemplate
      title="UK sick pay calculator"
      description="Estimate Statutory Sick Pay (SSP) for a period of sickness absence, week by week."
      sources={sickPaySources}
    >
      <SickPayCalculator />
    </CalculatorTemplate>
  );
}
