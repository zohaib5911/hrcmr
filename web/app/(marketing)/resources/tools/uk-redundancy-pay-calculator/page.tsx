import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { RedundancyPayCalculator } from "@/components/calculators/uk-redundancy-pay-calculator";
import { redundancySources } from "@/lib/calculators/uk-redundancy-pay-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/uk-redundancy-pay-calculator",
  "UK redundancy pay calculator",
  "Estimate statutory redundancy pay in Great Britain or Northern Ireland with age bands, completed service and capped weekly pay.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "Statutory redundancy pay generally depends on employee eligibility, completed years of service, age in each year and capped weekly pay. Contractual redundancy terms may offer more.",
  howItWorks: [
    {
      title: "Check the employment",
      body: "Choose the jurisdiction, employment status and reason for leaving.",
    },
    {
      title: "Enter dates and pay",
      body: "Use the relevant redundancy date and average gross weekly pay. Confirm disputed continuity or payment-in-lieu dates with an adviser.",
    },
    {
      title: "Review the service bands",
      body: "The result applies the dated weekly cap and age bands to counted service. Notice and other final payments are separate.",
    },
  ],
  faq: [
    {
      question: "Does every dismissal qualify?",
      answer:
        "No. Employee status, service and the reason for leaving matter. Misconduct and refusing suitable alternative work can affect entitlement.",
    },
    {
      question: "Is notice pay included?",
      answer: "No. Check notice pay, unused holiday and other contractual payments separately.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      slug="uk-redundancy-pay-calculator"
      content={content}
      title="UK redundancy pay calculator"
      description="Estimate the statutory minimum using your age, continuous service and weekly pay. Separate rules and pay caps apply in Great Britain and Northern Ireland."
      sources={redundancySources}
    >
      <RedundancyPayCalculator />
    </CalculatorTemplate>
  );
}
