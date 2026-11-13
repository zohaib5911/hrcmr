import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { EmployerCostCalculator } from "@/components/calculators/uk-employer-cost-calculator";
import { employerCostSources } from "@/lib/calculators/uk-employer-cost-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/uk-employer-cost-calculator",
  "UK employer cost calculator",
  "Estimate annual UK employer National Insurance, pension contributions and total salary cost, with an Apprenticeship Levy note.",
);
const content: CalculatorFrameContent = {
  quickAnswer:
    "The cost of employing someone includes gross salary plus employer National Insurance and any employer pension contribution. This estimate shows those annual costs before employer-wide allowances.",
  howItWorks: [
    {
      title: "Describe the employee",
      body: "Choose the tax year, salary, age and whether an eligible recognised apprenticeship applies.",
    },
    {
      title: "Set the pension basis",
      body: "Use the employer contribution and earnings basis agreed with the pension scheme. This tool does not decide enrolment eligibility.",
    },
    {
      title: "Review the budget",
      body: "Compare salary, NI and pension as you edit. Read the separate Apprenticeship Levy note before budgeting across the organisation.",
    },
  ],
  faq: [
    {
      question: "Is Employment Allowance deducted?",
      answer:
        "No. Eligibility and use of the allowance are assessed across the employer, so it is excluded from this employee estimate.",
    },
    {
      question: "Does the total include every hiring cost?",
      answer:
        "No. Benefits, bonuses, equipment and other business costs are outside this estimate; confirm pension and NI relief eligibility separately.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      slug="uk-employer-cost-calculator"
      content={content}
      title="UK employer cost calculator"
      description="Estimate annual salary, employer National Insurance and pension costs for an employee or recognised apprentice."
      sources={employerCostSources}
    >
      <EmployerCostCalculator />
    </CalculatorTemplate>
  );
}
