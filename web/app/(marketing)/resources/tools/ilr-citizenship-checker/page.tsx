import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { IlrCitizenshipChecker } from "@/components/calculators/ilr-citizenship-checker";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { settlementRoutes, settlementSources } from "@/lib/calculators/ilr-citizenship-checker";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/ilr-citizenship-checker",
  "ILR and citizenship checker",
  "Explore conditional settlement and British citizenship residence milestones across 14 visa pathways, with absence checks and official sources.",
);

const skilledWorkerYears = settlementRoutes.find((route) => route.id === "skilled_worker")?.years;

const content: CalculatorFrameContent = {
  quickAnswer: `Work routes such as Skilled Worker lead to settlement (ILR) after ${skilledWorkerYears} years of qualifying residence; other routes have their own periods. British citizenship usually follows after a further period of settled status, and absences abroad must stay within set limits.`,
  howItWorks: [
    {
      title: "Choose your pathway and dates",
      body: "Pick the visa pathway, the first day of qualifying residence and when your UK residence began. Add the actual ILR grant date if you have one.",
    },
    {
      title: "Enter your absences",
      body: "Count whole days abroad from your travel records for each period. The tool compares them with the limits published for settlement and citizenship.",
    },
    {
      title: "Read the conditional timeline",
      body: "You see the qualifying-residence milestone for ILR and the earliest citizenship residence date. Absences over the limits, or routes without a rolling check, are flagged for individual review.",
    },
  ],
  faq: [
    {
      question: "Is the ILR date the day I can apply?",
      answer:
        "Not necessarily. It is the full qualifying-residence anniversary. Gaps, lawful status, salary and other route conditions can change when you can apply, and a grant is never guaranteed.",
    },
    {
      question: "Does being married to a British citizen change the timeline?",
      answer:
        "It can. Spouses and civil partners of British citizens usually have a shorter residence period for citizenship and don’t need to wait after settlement.",
    },
    {
      question: "What if my absences are over the limits?",
      answer:
        "The tool flags the result for review rather than giving a verdict. Some absences can be excused at the Home Office’s discretion, so get individual advice.",
    },
    {
      question: "Is anything I enter stored?",
      answer: "No. The check runs in your browser and nothing is saved or sent.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="ILR and citizenship checker"
      description="Plan a conditional residence timeline across 14 pathways. Dates depend on qualifying residence, an actual settlement grant and all other immigration requirements."
      sources={settlementSources}
      slug="ilr-citizenship-checker"
      content={content}
    >
      <IlrCitizenshipChecker />
    </CalculatorTemplate>
  );
}
