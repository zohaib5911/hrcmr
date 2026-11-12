import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { RightToWorkChecker } from "@/components/calculators/right-to-work-checker";
import { rightToWorkSource } from "@/lib/calculators/right-to-work-october-2026-checker";

export const metadata: Metadata = {
  title: "Right-to-work October 2026 checker",
  description:
    "Check how the October 2026 right-to-work rules may apply to employees, workers, individual sub-contractors and online matching services.",
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="Right-to-work October 2026 checker"
      description="Understand direct checks and extended liability for your working arrangement under the October 2026 Home Office guidance."
      sources={[rightToWorkSource]}
    >
      <RightToWorkChecker />
    </CalculatorTemplate>
  );
}
