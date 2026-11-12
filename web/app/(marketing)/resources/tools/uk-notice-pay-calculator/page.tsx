import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { UkNoticePayCalculator } from "@/components/calculators/uk-notice-pay-calculator";
import {
  noticeGbSource,
  noticeNiSource,
  resignationSource,
} from "@/lib/calculators/uk-notice-pay-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/uk-notice-pay-calculator",
  "UK notice pay calculator",
  "Compare statutory and contractual notice and work out gross notice pay, garden leave and payment in lieu of notice.",
);

export default function Page() {
  return (
    <CalculatorTemplate
      title="UK notice pay calculator"
      description="Enter the dates, your contract notice and pay to see the notice that applies, the last day and the gross notice pay."
      sources={[noticeGbSource, noticeNiSource, resignationSource]}
    >
      <UkNoticePayCalculator />
    </CalculatorTemplate>
  );
}
