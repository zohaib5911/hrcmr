import {
  BellRing,
  BadgeCheck,
  ClipboardCheck,
  FileSearch,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import type { Metadata } from "next";

import { brand } from "@brand";

import { Faq } from "@/components/marketing/faq";
import {
  Band,
  CtaBand,
  FeatureGrid,
  Hero,
  Section,
  SectionHeading,
} from "@/components/marketing/sections";
import { SIGN_UP } from "@/lib/marketing-nav";

export const metadata: Metadata = {
  title: "Sponsor licence compliance",
  description: `How ${brand.name} helps a UK sponsor licence holder keep records and meet reporting duties.`,
};

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "One list of what needs attention",
    body: "Expiring visas, missing records and reports due, brought together and ordered by date.",
  },
  {
    icon: BadgeCheck,
    title: "Right to work checks",
    body: "Each check recorded with its evidence, and a reminder before any follow-up check.",
  },
  {
    icon: BellRing,
    title: "Reporting duties",
    body: "Record a change and see the deadline counted in working days for your nation.",
  },
  {
    icon: UserCog,
    title: "Key personnel",
    body: "Keep the details of your authorising officer, key contact and level 1 user up to date.",
  },
  {
    icon: ClipboardCheck,
    title: "Inspection readiness",
    body: "A short checklist of the records an inspector is likely to ask for, with what is missing.",
  },
  {
    icon: FileSearch,
    title: "Job and salary check",
    body: "Find the occupation code for a role and see the salary table for the Skilled Worker route.",
  },
] as const;

const FAQ = [
  {
    question: "Does it give legal or immigration advice?",
    answer:
      "No. It helps you keep records and see dates. Every rule it shows has its source and the date it was last checked. For a decision that matters, take advice from a solicitor or an adviser regulated for immigration.",
  },
  {
    question: "Does it report to the Home Office for me?",
    answer:
      "No. You report through the Sponsor Management System as usual. It tells you what to report and by when, and keeps your reference once you have.",
  },
  {
    question: "Can I use it if I do not hold a licence?",
    answer: "Yes. The HR parts work for any employer, and the sponsor parts stay out of the way.",
  },
] as const;

export default function SponsorCompliancePage() {
  return (
    <>
      <Hero
        eyebrow="Sponsor licence compliance"
        title="Keep your licence in good order"
        lead="A licence comes with duties. Know what they are, see what is due and keep the proof."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
      <Section tone="raised" label="What it does">
        <FeatureGrid features={FEATURES} />
      </Section>
      <Band
        tone="page"
        eyebrow="Reporting duties"
        title="Never miss a report"
        lead="Some changes must be reported within a set number of working days. Record the change and the deadline is worked out for you."
        points={[
          "Ten working days for changes to a worker's situation.",
          "Twenty working days for changes to your organisation.",
          "A record of when it was reported and under what reference.",
        ]}
        actions={[
          {
            label: "Read about reporting duties",
            href: "/sponsor-licence-compliance/reporting-duties" as never,
          },
        ]}
      />
      <Section tone="raised" id="faq">
        <SectionHeading title="Questions people ask" className="mb-10" />
        <Faq items={FAQ} />
      </Section>
      <CtaBand
        title="Get ready before the next visit"
        lead="Start on the free plan. No card needed."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
