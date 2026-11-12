import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { HolidayEntitlementCalculator } from "@/components/calculators/holiday-entitlement-calculator";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { holidaySources } from "@/lib/calculators/holiday-entitlement-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/holiday-entitlement-calculator",
  "Holiday entitlement calculator",
  "Work out statutory holiday for part-time, part-year and irregular-hours workers in days or hours, with workings.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "Almost all workers get 5.6 weeks of paid holiday a year. Someone working 5 days a week gets 28 days; part-time workers get the same 5.6 weeks pro rata, capped at 28 days.",
  howItWorks: [
    {
      title: "Choose how they work",
      body: "Regular days, regular hours, starting or leaving part way through the year, or irregular hours.",
    },
    {
      title: "Enter their working pattern",
      body: "Days or hours a week, or the hours worked in the pay period for irregular-hours workers.",
    },
    {
      title: "Read the workings",
      body: "Regular patterns are multiplied by 5.6 weeks (capped at 28 days). Part-year leave is pro rata to the days employed. Irregular hours accrue at 12.07% of hours worked.",
    },
  ],
  faq: [
    {
      question: "Are bank holidays included?",
      answer:
        "They can be. Employers may count bank holidays as part of the 5.6 weeks; the contract says whether any are on top.",
    },
    {
      question: "Who is an irregular-hours worker?",
      answer:
        "For leave years starting on or after 1 April 2024, someone whose paid hours vary wholly or mostly from week to week, or who works only part of the year. Their holiday accrues at 12.07% of hours worked.",
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
      title="Holiday entitlement calculator"
      description="Work out statutory annual leave for regular, part-year and irregular-hours workers, with the workings shown."
      sources={holidaySources}
      slug="holiday-entitlement-calculator"
      content={content}
    >
      <HolidayEntitlementCalculator />
    </CalculatorTemplate>
  );
}
