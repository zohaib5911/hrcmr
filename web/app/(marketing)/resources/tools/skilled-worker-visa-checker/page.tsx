import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SkilledWorkerVisaChecker } from "@/components/calculators/skilled-worker-visa-checker";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { visaCheckerSources } from "@/lib/calculators/skilled-worker-visa-checker";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/skilled-worker-visa-checker",
  "Skilled Worker visa checker",
  "Check whether a job and salary meet the Skilled Worker visa rules: minimum salary for each points option, dependant funds and English level.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "A Skilled Worker job must be an eligible occupation and pay at least both a general salary threshold and the occupation’s going rate, pro rata to the hours. A relevant PhD, being a new entrant or a job on the Immigration Salary List can lower the amounts.",
  howItWorks: [
    {
      title: "Find the job",
      body: "Search by SOC 2020 code or job title and choose the occupation. Only this search is sent to the public occupation lookup.",
    },
    {
      title: "Enter the salary and hours",
      body: "Use guaranteed basic gross pay. Going rates are adjusted for the weekly hours, and only pay for a capped number of hours counts.",
    },
    {
      title: "Describe the applicant",
      body: "Their situation, a relevant PhD or new-entrant status decide which points options (A to E) can apply.",
    },
    {
      title: "Read each option",
      body: "The result shows the minimum salary for each option and whether it is met, plus the funds needed for dependants and the English level. Roles the tool doesn’t model show as needs review.",
    },
  ],
  faq: [
    {
      question: "Does a met salary mean the visa will be granted?",
      answer:
        "No. Salary is one requirement. The sponsor, the certificate of sponsorship, English, funds and other rules all apply, and the Home Office makes the decision.",
    },
    {
      question: "Why does my nursing or teaching role say needs review?",
      answer:
        "Many health and education roles are paid on national pay scales and use other options. The tool doesn’t give a verdict for them; check the official Skilled Occupations appendix.",
    },
    {
      question: "Can bonuses or allowances count towards the salary?",
      answer:
        "Usually not. Only guaranteed basic gross pay counts, so leave out overtime, bonuses and most allowances.",
    },
    {
      question: "What is sent when I use this tool?",
      answer:
        "Only the job title or SOC code you search for goes to the public occupation lookup. The example scenarios use data built into the page. Salary and personal answers stay in this page and are not saved.",
    },
  ],
};

export default function Page() {
  return (
    <CalculatorTemplate
      title="Skilled Worker visa checker"
      description="Find the SOC 2020 code for a job and see the minimum salary under each Skilled Worker points option."
      sources={visaCheckerSources}
      privacy="soc_lookup"
      slug="skilled-worker-visa-checker"
      content={content}
    >
      <SkilledWorkerVisaChecker />
    </CalculatorTemplate>
  );
}
