import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SponsorReportingDeadlineCalculator } from "@/components/calculators/sponsor-reporting-deadline-calculator";
import {
  bankHolidaysSource,
  sponsorDutiesSource,
} from "@/lib/calculators/sponsor-reporting-deadline-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/sponsor-reporting-deadline-calculator",
  "Sponsor reporting deadline calculator",
  "Work out the 10 or 20 working day deadline for reporting a change to the Home Office, using your nation’s bank holidays.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="Sponsor reporting deadline calculator"
      description="Pick the event, its date and your nation to see the latest date to report it, and how many working days are left."
      sources={[sponsorDutiesSource, bankHolidaysSource]}
    >
      <SponsorReportingDeadlineCalculator />
    </CalculatorTemplate>
  );
}
