import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { UkTakeHomeSalaryCalculator } from "@/components/calculators/uk-take-home-salary-calculator";
import { takeHomeSources } from "@/lib/calculators/uk-take-home-salary-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/uk-take-home-salary-calculator",
  "UK take-home salary calculator",
  "Estimate annual, monthly and weekly take-home pay for England, Scotland and Wales after tax, National Insurance, pension and student loans.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "Your take-home pay is what remains after income tax, employee National Insurance and the deductions you select. The tax year, region and tax code can change the estimate.",
  howItWorks: [
    {
      title: "Choose the tax rules",
      body: "Select the tax year and region, then check the tax code and NI category against your payslip.",
    },
    {
      title: "Add pay and deductions",
      body: "Enter annual salary, pension method and any student loans or other deductions.",
    },
    {
      title: "Compare the breakdown",
      body: "Results update as you edit. Annual totals are divided into monthly and weekly estimates; payroll rounding can differ.",
    },
  ],
  faq: [
    {
      question: "Is this a payslip calculation?",
      answer:
        "No. This is an annual estimate for a steady salary. Emergency codes, changing pay and complex circumstances need a payroll calculation.",
    },
    {
      question: "Why does Scotland have different results?",
      answer:
        "Scottish income tax bands apply to relevant earnings. National Insurance and student loans are calculated separately.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      slug="uk-take-home-salary-calculator"
      content={content}
      title="UK take-home salary calculator"
      description="Estimate take-home pay for 2025 to 2026 or 2026 to 2027 after income tax, National Insurance, pension and student loans, with a breakdown."
      sources={takeHomeSources}
    >
      <UkTakeHomeSalaryCalculator />
    </CalculatorTemplate>
  );
}
