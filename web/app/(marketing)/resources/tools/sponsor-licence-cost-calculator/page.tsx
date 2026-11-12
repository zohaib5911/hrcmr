import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { CalculatorTemplate } from "@/components/calculators/calculator-template";
import { SponsorLicenceCostCalculator } from "@/components/calculators/sponsor-licence-cost-calculator";
import type { CalculatorFrameContent } from "@/lib/calculators/frame";
import { sponsorCostSources } from "@/lib/calculators/sponsor-licence-cost-calculator";

export const metadata: Metadata = pageMetadata(
  "/resources/tools/sponsor-licence-cost-calculator",
  "Sponsor licence cost calculator",
  "Estimate sponsor licence, certificate of sponsorship, Immigration Skills Charge, visa and healthcare surcharge costs.",
);

const content: CalculatorFrameContent = {
  quickAnswer:
    "Sponsoring a worker costs the employer a licence fee, a certificate of sponsorship and the Immigration Skills Charge. The worker side adds the visa fee and the healthcare surcharge for each person. Small companies and charities pay less for the licence and the skills charge.",
  howItWorks: [
    {
      title: "Describe your organisation",
      body: "Charities and companies that meet at least 2 of the small-company tests (turnover, assets, employees) pay the small sponsor rates.",
    },
    {
      title: "Set the role and certificate",
      body: "The route, where the worker applies from, the certificate length and the occupation code set the skills charge, visa fee tier and any exemptions.",
    },
    {
      title: "Add workers, dependants and fees",
      body: "Each dependant pays their own visa fee and healthcare surcharge. Faster decisions are optional extra fees.",
    },
    {
      title: "Compare the totals",
      body: "The result splits employer and worker-side costs and compares other certificate lengths. Every amount comes from the dated GOV.UK fee tables in the sources.",
    },
  ],
  faq: [
    {
      question: "Can the worker pay the sponsorship costs?",
      answer:
        "No. The licence fee, certificate fee and Immigration Skills Charge must be paid by the sponsor. Employers may choose to cover visa fees and the healthcare surcharge.",
    },
    {
      question: "Why does the certificate length change the healthcare surcharge?",
      answer:
        "The surcharge is charged per year of the visa, and the visa normally runs a little past the certificate end date. Longer certificates also cost more in skills charge.",
    },
    {
      question: "Is this the exact amount we will pay?",
      answer:
        "It is an estimate from the published fees. Fees change, and individual circumstances such as earlier visa grants can change the surcharge.",
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
      title="Sponsor licence cost calculator"
      description="Estimate what sponsoring a worker costs the employer and the worker, and compare certificate lengths."
      sources={sponsorCostSources}
      slug="sponsor-licence-cost-calculator"
      content={content}
    >
      <SponsorLicenceCostCalculator />
    </CalculatorTemplate>
  );
}
