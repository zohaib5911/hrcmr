import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SkilledWorkerVisaChecker } from "@/components/calculators/skilled-worker-visa-checker";
import { visaCheckerSources } from "@/lib/calculators/skilled-worker-visa-checker";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/skilled-worker-visa-checker",
  "Skilled Worker visa checker",
  "Check whether a job and salary meet the Skilled Worker visa rules: minimum salary for each points option, dependant funds and English level.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="Skilled Worker visa checker"
      description="Find the SOC 2020 code for a job and see the minimum salary under each Skilled Worker points option."
      sources={visaCheckerSources}
      privacy="soc_lookup"
    >
      <SkilledWorkerVisaChecker />
    </CalculatorTemplate>
  );
}
