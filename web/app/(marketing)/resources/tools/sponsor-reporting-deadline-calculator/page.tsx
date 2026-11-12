import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SponsorReportingDeadlineCalculator } from "@/components/calculators/sponsor-reporting-deadline-calculator";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import {
  bankHolidaysSource,
  sponsorDutiesSource,
} from "@/lib/calculators/sponsor-reporting-deadline-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/sponsor-reporting-deadline-calculator",
  "Sponsor reporting deadline calculator",
  "Work out the 10 or 20 working day deadline for reporting a change to the Home Office, using your nation’s bank holidays.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "Most changes about a sponsored worker must be reported on the sponsor management system within 10 working days. Most changes to your organisation have 20 working days. Weekends and bank holidays in your nation don’t count.",
  howItWorks: [
    {
      title: "Choose the event",
      body: "Pick what happened. Each event links to the paragraph of the sponsor guidance that sets its reporting period, and some events have no fixed deadline.",
    },
    {
      title: "Enter the date and your nation",
      body: "Use the date the event happened, or when you became aware of it for organisation changes. The nation sets which bank holidays are skipped.",
    },
    {
      title: "Read the deadline",
      body: "The event day isn’t counted. The tool adds the working days to find the latest date to report and how many working days are left from today.",
    },
  ],
  faq: [
    {
      question: "Should I wait until the deadline to report?",
      answer:
        "No. The deadline is the latest date. Report as soon as you can, and keep a record of when you reported.",
    },
    {
      question: "Why does my nation matter?",
      answer:
        "England and Wales, Scotland and Northern Ireland have different bank holidays, so the same event can have a different deadline.",
    },
    {
      question: "Why can’t I see a deadline for some dates?",
      answer:
        "The tool only holds official bank holiday dates for a set range. Outside it, it won’t guess a date.",
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
      title="Sponsor reporting deadline calculator"
      description="Pick the event, its date and your nation to see the latest date to report it, and how many working days are left."
      sources={[sponsorDutiesSource, bankHolidaysSource]}
      slug="sponsor-reporting-deadline-calculator"
      content={content}
    >
      <SponsorReportingDeadlineCalculator />
    </CalculatorTemplate>
  );
}
