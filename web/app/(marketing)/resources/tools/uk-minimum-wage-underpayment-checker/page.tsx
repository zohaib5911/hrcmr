import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { MinimumWageChecker } from "@/components/calculators/uk-minimum-wage-underpayment-checker";
import { wageSources } from "@/lib/calculators/uk-minimum-wage-underpayment-checker";
import { pageMetadata } from "@/lib/seo";
export const metadata = pageMetadata(
  "/resources/tools/uk-minimum-wage-underpayment-checker",
  "UK minimum wage underpayment checker",
  "Compare pay-period earnings with UK minimum wage rates, including work costs, tips and accommodation adjustments.",
);
const content: CalculatorFrameContent = {
  quickAnswer:
    "Minimum-wage compliance compares counted pay with qualifying hours for a pay reference period. Deductions, work costs and accommodation can change the comparison even when the headline hourly pay looks sufficient.",
  howItWorks: [
    {
      title: "Select the period and worker",
      body: "Choose pay type, frequency, start date, age and apprenticeship status at the period start.",
    },
    {
      title: "Enter counted hours and pay",
      body: "Use the hours allocated under minimum-wage rules and gross period pay, with each reduction entered only once.",
    },
    {
      title: "Review the comparison",
      body: "The dated rate is selected locally. A potential shortfall is a prompt to review payroll records and the official rules, not a final enforcement calculation.",
    },
  ],
  faq: [
    {
      question: "Should I subtract income tax?",
      answer: "No. Do not subtract income tax or National Insurance for this comparison.",
    },
    {
      question: "Do tips count towards minimum wage?",
      answer:
        "No. If tips were included in the gross pay entered, identify them in the tips field so the tool excludes them once.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      slug="uk-minimum-wage-underpayment-checker"
      content={content}
      title="UK minimum wage underpayment checker"
      description="Estimate effective hourly pay and any shortfall for one pay reference period."
      sources={wageSources}
    >
      <MinimumWageChecker />
    </CalculatorTemplate>
  );
}
