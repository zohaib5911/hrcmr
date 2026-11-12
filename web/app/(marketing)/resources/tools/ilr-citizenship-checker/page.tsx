import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { IlrCitizenshipChecker } from "@/components/calculators/ilr-citizenship-checker";
import { settlementSources } from "@/lib/calculators/ilr-citizenship-checker";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/ilr-citizenship-checker",
  "ILR and citizenship checker",
  "Explore conditional settlement and British citizenship residence milestones across 14 visa pathways, with absence checks and official sources.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="ILR and citizenship checker"
      description="Plan a conditional residence timeline across 14 pathways. Dates depend on qualifying residence, an actual settlement grant and all other immigration requirements."
      sources={settlementSources}
    >
      <IlrCitizenshipChecker />
    </CalculatorTemplate>
  );
}
