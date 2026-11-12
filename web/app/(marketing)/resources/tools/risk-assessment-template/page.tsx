import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import { RiskAssessmentTemplate } from "@/components/calculators/risk-assessment-template";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/risk-assessment-template",
  "Risk assessment template",
  "Fill in a workplace risk assessment and download it as PDF or Word. Your draft is kept only in your browser.",
);
export default function Page() {
  return (
    <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
      <header className="pb-8">
        <h1 className="text-large-title text-label">Risk assessment template</h1>
        <p className="text-callout text-label-secondary mt-3 max-w-2xl">
          Record hazards, controls and actions, then download a PDF or Word copy.
        </p>
        <p className="text-footnote text-label-secondary mt-3">
          Your draft is saved only in this browser (local storage) and is never sent anywhere. Clear
          it at any time. General guidance only; it does not replace professional health and safety
          advice. See the HSE’s guidance at{" "}
          <a
            href="https://www.hse.gov.uk/simple-health-safety/risk/"
            className="text-accent-text underline"
          >
            hse.gov.uk
          </a>
          .
        </p>
      </header>
      <RiskAssessmentTemplate />
    </div>
  );
}
