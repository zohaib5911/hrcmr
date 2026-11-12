import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SkilledWorkerIlrSalaryCalculator } from "@/components/calculators/skilled-worker-ilr-salary-calculator";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import {
  FULL_TIME_HOURS,
  ilrSalarySources,
} from "@/lib/calculators/skilled-worker-ilr-salary-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/skilled-worker-ilr-salary-calculator",
  "Skilled Worker ILR salary calculator",
  "Find the salary a Skilled Worker or Health and Care Worker must be paid to apply for indefinite leave to remain.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "To settle on the Skilled Worker route you must be paid at least the higher of a fixed minimum salary and the full going rate for your job when you apply. The lower 70%, 80% and 90% going rates used for some visas don’t apply to settlement.",
  howItWorks: [
    {
      title: "Find your job",
      body: "Search by job title or 4-digit SOC code in the occupation table built into this page. Nothing is sent while you search.",
    },
    {
      title: "Choose your situation and hours",
      body: `Health and Care, Immigration Salary List, transitional and sportsperson cases use different rules. Going rates are for a ${FULL_TIME_HOURS}-hour week and are pro-rated by your stated hours; the fixed minimum is not.`,
    },
    {
      title: "Read the requirement",
      body: "You see the fixed minimum, the going rate for your hours and the higher of the two. Pay-scale jobs and situations without a published figure show guidance instead of an amount.",
    },
  ],
  faq: [
    {
      question: "Does meeting the salary mean I will get ILR?",
      answer:
        "No. Salary is one requirement. Continuous residence, absences, Life in the UK, English and your sponsor’s confirmation all matter, and the Home Office decides.",
    },
    {
      question: "Why is my figure higher than for my visa?",
      answer:
        "Settlement uses the full going rate. Discounts you may have had for your visa, such as new entrant or PhD rates, don’t carry over.",
    },
    {
      question: "What counts as salary?",
      answer:
        "Guaranteed basic gross pay from your sponsor. Overtime, bonuses and most allowances don’t count.",
    },
    {
      question: "Is anything I enter stored?",
      answer: "No. The calculation runs in your browser and nothing is saved or sent.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="Skilled Worker ILR salary calculator"
      description="Find the salary you must be paid when you apply to settle, based on your job and working hours."
      sources={ilrSalarySources}
      slug="skilled-worker-ilr-salary-calculator"
      content={content}
    >
      <SkilledWorkerIlrSalaryCalculator />
    </CalculatorTemplate>
  );
}
