import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { MinimumWageChecker } from "@/components/calculators/uk-minimum-wage-underpayment-checker";
import { wageSources } from "@/lib/calculators/uk-minimum-wage-underpayment-checker";
import { pageMetadata } from "@/lib/seo";
export const metadata = pageMetadata(
  "/resources/tools/uk-minimum-wage-underpayment-checker",
  "UK minimum wage underpayment checker",
  "Compare pay-period earnings with UK minimum wage rates, including work costs, tips and accommodation adjustments.",
);
export default function Page() {
  return (
    <CalculatorTemplate
      title="UK minimum wage underpayment checker"
      description="Estimate effective hourly pay and any shortfall for one pay reference period."
      sources={wageSources}
    >
      <MinimumWageChecker />
    </CalculatorTemplate>
  );
}
