import { pageMetadata } from "@/lib/seo";
import { FileCheck2, KeyRound, Lock, ScrollText, ShieldCheck, Users } from "lucide-react";
import type { Metadata } from "next";

import { brand } from "@brand";

import {
  CtaBand,
  FeatureGrid,
  Hero,
  Section,
  SectionHeading,
} from "@/components/marketing/sections";

export const metadata: Metadata = pageMetadata(
  "/security",
  "Security",
  `How ${brand.name} protects your people's records.`,
);

const FEATURES = [
  {
    icon: Lock,
    title: "Encrypted details",
    body: "Sensitive details such as passport and national insurance numbers are encrypted before they are stored.",
  },
  {
    icon: Users,
    title: "Companies kept apart",
    body: "Every company's data is separated from every other's by the database itself, not only by the application.",
  },
  {
    icon: KeyRound,
    title: "Two-step sign-in",
    body: "Use an authenticator app to protect accounts. A company can require it for administrators or for everyone.",
  },
  {
    icon: ScrollText,
    title: "An audit trail",
    body: "Every change is written down with who made it and when, and administrators can read it.",
  },
  {
    icon: FileCheck2,
    title: "Scanned uploads",
    body: "Files are checked for viruses and for their real type before they are kept.",
  },
  {
    icon: ShieldCheck,
    title: "Access by role",
    body: "People see only what their role allows. Managers see their team; employees see themselves.",
  },
] as const;

export default function SecurityPage() {
  return (
    <>
      <Hero
        eyebrow="Security"
        title="Careful with what you trust us with"
        lead="HR records are personal. These are the protections built into the product, described plainly."
      />
      <Section tone="raised" label="Protections">
        <FeatureGrid features={FEATURES} />
      </Section>
      <Section tone="page" id="your-data">
        <SectionHeading
          title="Your data stays yours"
          lead="You can export everything at any time, and you can ask for your account and its data to be deleted. Deletion has a short waiting period so it cannot happen by accident."
        />
      </Section>
      <Section tone="raised" id="report">
        <SectionHeading
          title="Found a problem?"
          lead="Tell us through the contact page and choose the topic that fits. We reply within one working day. Please give us a reasonable time to fix an issue before you share it."
        />
      </Section>
      <CtaBand
        title="Questions about how we handle data?"
        lead="Ask us. We will answer in plain words."
        actions={[{ label: "Contact us", href: "/contact" as never }]}
      />
    </>
  );
}
