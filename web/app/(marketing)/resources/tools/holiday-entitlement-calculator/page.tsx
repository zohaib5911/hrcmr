import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { HolidayEntitlementCalculator } from "@/components/calculators/holiday-entitlement-calculator";
import { holidaySources } from "@/lib/calculators/holiday-entitlement-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/holiday-entitlement-calculator",
  "Holiday entitlement calculator",
  "Work out statutory holiday for part-time, part-year and irregular-hours workers in days or hours, with workings.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="Holiday entitlement calculator"
      description="Work out statutory annual leave for regular, part-year and irregular-hours workers, with the workings shown."
      sources={holidaySources}
    >
      <HolidayEntitlementCalculator />
    </CalculatorTemplate>
  );
}
