import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { RightToWorkChecker } from "@/components/calculators/right-to-work-checker";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { rightToWorkSource } from "@/lib/calculators/right-to-work-october-2026-checker";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/right-to-work-october-2026-checker",
  "Right-to-work October 2026 checker",
  "Check how the October 2026 right-to-work rules may apply to employees, workers, individual sub-contractors and online matching services.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "Employers must check that every employee is allowed to work in the UK before they start. The October 2026 guidance extends liability to some workers, individual sub-contractors and online matching services, depending on how the arrangement actually works.",
  howItWorks: [
    {
      title: "Describe the arrangement",
      body: "Choose the engagement type and confirm the work is carried out in the UK. Work done wholly overseas is outside this scheme.",
    },
    {
      title: "Check who does the work and when",
      body: "Say whether you buy directly from an independent business, and give the start date. The start date is compared with the commencement date in the guidance.",
    },
    {
      title: "Look at contracts and substitution",
      body: "Contract chains, online matching and permitted substitution can bring extended liability, judged from the date that arrangement was entered into.",
    },
    {
      title: "Read the scope check",
      body: "Each duty shows as in scope, outside scope, predates commencement or needs review, with the actions and records the guidance expects. Unanswered questions stay as needs review.",
    },
  ],
  faq: [
    {
      question: "Does this confirm that someone can work for us?",
      answer:
        "No. It only shows which duties may apply to the arrangement. You still need a prescribed check of the individual before work starts to have a statutory excuse.",
    },
    {
      question: "Is a self-employed label enough to put someone outside scope?",
      answer:
        "No. The guidance looks at how the arrangement works in practice, such as who personally does the work and whether the provider really operates as an independent business.",
    },
    {
      question: "What if the arrangement started before the commencement date?",
      answer:
        "The result shows it as predating commencement. Renewals or changes to the arrangement are assessed separately, and other legal duties still apply.",
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
      title="Right-to-work October 2026 checker"
      description="Understand direct checks and extended liability for your working arrangement under the October 2026 Home Office guidance."
      sources={[rightToWorkSource]}
      slug="right-to-work-october-2026-checker"
      content={content}
    >
      <RightToWorkChecker />
    </CalculatorTemplate>
  );
}
