import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { RiskAssessmentTemplate } from "@/components/calculators/risk-assessment-template";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/risk-assessment-template",
  "Risk assessment template",
  "Fill in a workplace risk assessment and download it as PDF or Word. Your draft is kept only in your browser.",
);
const content: CalculatorFrameContent = {
  quickAnswer:
    "A useful risk assessment records workplace hazards, who could be harmed, controls and further actions. Start with the work as it is actually done, then assign owners and review the controls.",
  howItWorks: [
    {
      title: "Describe the assessment",
      body: "Identify the organisation, site, activity, assessor and review date. Consult the people doing the work.",
    },
    {
      title: "Record hazards and actions",
      body: "Describe who could be harmed, existing controls, further actions and who will complete them.",
    },
    {
      title: "Preview and export",
      body: "Review your draft, complete the required fields and acknowledgement, then download PDF or Word. Clear the browser draft when finished.",
    },
  ],
  faq: [
    {
      question: "Is an example a completed assessment?",
      answer:
        "No. Examples are prompts only. Assess your own workplace and obtain competent advice for specialist or high-risk work.",
    },
    {
      question: "Where is my draft saved?",
      answer:
        "Only in this browser\u2019s local storage. It is never sent anywhere. Clear saved draft removes it from this browser; downloaded copies remain with you.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="Risk assessment template"
      description="Record workplace hazards, controls and actions, then download a PDF or Word copy. General guidance only; this does not replace professional health and safety advice."
      slug="risk-assessment-template"
      privacy="local_draft"
      content={content}
      sources={[
        {
          title: "HSE: Managing risks and risk assessment at work",
          url: "https://www.hse.gov.uk/simple-health-safety/risk/",
          checkedOn: "2026-11-13",
          validFrom: "2026-11-13",
          validTo: null,
        },
      ]}
    >
      <RiskAssessmentTemplate />
    </CalculatorTemplate>
  );
}
