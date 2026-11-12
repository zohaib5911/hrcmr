import type { Metadata } from "next";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { RedundancyPayCalculator } from "@/components/calculators/uk-redundancy-pay-calculator";
import { redundancySources } from "@/lib/calculators/uk-redundancy-pay-calculator";

export const metadata: Metadata = {
  title: "UK redundancy pay calculator",
  description:
    "Estimate statutory redundancy pay in Great Britain or Northern Ireland with age bands, completed service and capped weekly pay.",
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="UK redundancy pay calculator"
      description="Estimate the statutory minimum using your age, continuous service and weekly pay. Separate rules and pay caps apply in Great Britain and Northern Ireland."
      sources={redundancySources}
    >
      <RedundancyPayCalculator />
    </CalculatorTemplate>
  );
}
