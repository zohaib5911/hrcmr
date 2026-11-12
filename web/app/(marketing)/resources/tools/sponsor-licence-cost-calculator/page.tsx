import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SponsorLicenceCostCalculator } from "@/components/calculators/sponsor-licence-cost-calculator";
import { sponsorCostSources } from "@/lib/calculators/sponsor-licence-cost-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/sponsor-licence-cost-calculator",
  "Sponsor licence cost calculator",
  "Estimate sponsor licence, certificate of sponsorship, Immigration Skills Charge, visa and healthcare surcharge costs.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="Sponsor licence cost calculator"
      description="Estimate what sponsoring a worker costs the employer and the worker, and compare certificate lengths."
      sources={sponsorCostSources}
    >
      <SponsorLicenceCostCalculator />
    </CalculatorTemplate>
  );
}
