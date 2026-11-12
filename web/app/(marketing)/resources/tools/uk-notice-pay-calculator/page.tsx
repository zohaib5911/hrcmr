import type { CalculatorFrameContent } from "@/lib/calculators/frame";
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

const content: CalculatorFrameContent = {
  quickAnswer:
    "Notice depends on who gives it, employee status, length of service and the contract. Compare the statutory period with contractual notice before estimating gross notice pay.",
  howItWorks: [
    {
      title: "Choose the situation",
      body: "Select the jurisdiction, who gives notice and employment status.",
    },
    {
      title: "Enter dates and terms",
      body: "Add the employment start, notice date, contract notice and average pay.",
    },
    {
      title: "Check the arrangement",
      body: "Compare notice weeks, estimated last day and gross pay for worked notice, garden leave or payment in lieu. Check the contract before acting.",
    },
  ],
  faq: [
    {
      question: "Can a contract give longer notice?",
      answer:
        "Yes. A longer contractual period can apply; the statutory minimum is a floor for eligible employees.",
    },
    {
      question: "Is payment in lieu automatic?",
      answer:
        "No. Check the contract and the agreement with the employer. Benefits, tax and disputed dismissal circumstances need separate review.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      slug="uk-notice-pay-calculator"
      content={content}
      title="UK notice pay calculator"
      description="Enter the dates, your contract notice and pay to see the notice that applies, the last day and the gross notice pay."
      sources={[noticeGbSource, noticeNiSource, resignationSource]}
    >
      <UkNoticePayCalculator />
    </CalculatorTemplate>
  );
}
