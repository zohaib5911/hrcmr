import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SkilledWorkerIlrSalaryCalculator } from "@/components/calculators/skilled-worker-ilr-salary-calculator";
import { ilrSalarySources } from "@/lib/calculators/skilled-worker-ilr-salary-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/skilled-worker-ilr-salary-calculator",
  "Skilled Worker ILR salary calculator",
  "Find the salary a Skilled Worker or Health and Care Worker must be paid to apply for indefinite leave to remain.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="Skilled Worker ILR salary calculator"
      description="Find the salary you must be paid when you apply to settle, based on your job and working hours."
      sources={ilrSalarySources}
    >
      <SkilledWorkerIlrSalaryCalculator />
    </CalculatorTemplate>
  );
}
