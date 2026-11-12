import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SickPayCalculator } from "@/components/calculators/uk-sick-pay-calculator";
import { sickPaySources } from "@/lib/calculators/uk-sick-pay-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/uk-sick-pay-calculator",
  "UK sick pay calculator",
  "Estimate Statutory Sick Pay for an absence, with a week-by-week table, under the rules from 6 April 2026.",
);
const content: CalculatorFrameContent = {
  quickAnswer:
    "Statutory Sick Pay is based on eligibility, normal working days, average earnings and the rules for the absence dates. This tool estimates one absence under the rules from 6 April 2026.",
  howItWorks: [
    {
      title: "Enter the absence",
      body: "Choose worker status and the first and last sickness dates. Mark a partly worked first day where relevant.",
    },
    {
      title: "Add earnings and working days",
      body: "Use average weekly earnings and the qualifying days normally worked.",
    },
    {
      title: "Check each week",
      body: "Review payable days and the week-by-week gross estimate. Prior or linked absences and excluded circumstances require a separate check.",
    },
  ],
  faq: [
    {
      question: "Does this include company sick pay?",
      answer: "No. A contract may provide additional sick pay; compare its terms separately.",
    },
    {
      question: "Can I use it for linked absences?",
      answer:
        "Linked periods and SSP already paid are not applied. Check the official guidance or payroll advice before paying.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      slug="uk-sick-pay-calculator"
      content={content}
      title="UK sick pay calculator"
      description="Estimate Statutory Sick Pay (SSP) for a period of sickness absence, week by week."
      sources={sickPaySources}
    >
      <SickPayCalculator />
    </CalculatorTemplate>
  );
}
