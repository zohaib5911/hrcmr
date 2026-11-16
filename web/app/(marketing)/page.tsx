import { StructuredData } from "@/components/marketing/structured-data";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import {
  BadgeCheck,
  Calculator,
  CalendarDays,
  Clock,
  FileText,
  GraduationCap,
  Lock,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { brand } from "@brand";

import { Faq } from "@/components/marketing/faq";
import { HeroShot } from "@/components/marketing/hero-shot";
import { ReminderPreview } from "@/components/marketing/reminder-preview";
import {
  Band,
  CtaBand,
  FeatureGrid,
  Hero,
  Section,
  SectionHeading,
} from "@/components/marketing/sections";
import { Icon } from "@/components/ui/icon";
import { SIGN_IN, SIGN_UP } from "@/lib/marketing-nav";

export const metadata: Metadata = pageMetadata(
  "/",
  "HR and sponsor compliance",
  "Keep HR records, right to work checks and sponsor duties together, with reminders for UK employers.",
);

const FAQ = [
  {
    question: "Do I need a sponsor licence to use it?",
    answer: `No. ${brand.name} works as a plain HR system for any UK employer. If you do sponsor workers, it adds the records and reminders a licence holder is expected to keep.`,
  },
  {
    question: "Does it give legal advice?",
    answer:
      "No. It helps you keep records and spot dates, and it shows its sources and the date they were checked. For a decision that matters, take advice from an immigration solicitor or adviser.",
  },
  {
    question: "Where is our data kept?",
    answer:
      "Sensitive details such as passport numbers are encrypted before they are stored, every company's data is kept apart from every other's, and every change is written to an audit trail you can read.",
  },
  {
    question: "Can I start without a card?",
    answer: "Yes. You can start on the free plan and move to a paid plan when you need to.",
  },
] as const;

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Sponsor compliance",
    body: "See what needs attention across your licence: expiring visas, reporting duties and missing records.",
  },
  {
    icon: BadgeCheck,
    title: "Right to work",
    body: "Record each check, keep the evidence with it, and be told before a follow-up check is due.",
  },
  {
    icon: CalendarDays,
    title: "Leave",
    body: "Requests, approvals and balances that take bank holidays into account.",
  },
  {
    icon: Clock,
    title: "Attendance and rota",
    body: "Clock in, plan the week's shifts and publish them to the people working them.",
  },
  {
    icon: FileText,
    title: "Documents and policies",
    body: "Keep company files with review dates, and see who has read and accepted each policy.",
  },
  {
    icon: GraduationCap,
    title: "Learning",
    body: "Assign short compliance courses, track who has finished them and keep the certificates.",
  },
] as const;

/** Short, true reasons to trust it (U6.1.8): each one links to where it is explained. */
const TRUST = [
  { icon: Lock, text: "Sensitive details encrypted", href: "/security" },
  { icon: ShieldCheck, text: "Every company's data kept apart", href: "/security" },
  { icon: Calculator, text: "Free employer tools", href: "/resources/tools" },
] as const;

function TrustRow() {
  return (
    <ul
      aria-label="Why employers trust it"
      className="flex flex-wrap justify-center gap-x-6 gap-y-3"
    >
      {TRUST.map((item) => (
        <li key={item.text}>
          <Link
            href={item.href}
            prefetch={false}
            className="text-callout text-label-secondary hover:text-label inline-flex items-center gap-2 underline-offset-2 hover:underline"
          >
            <Icon icon={item.icon} size={16} />
            {item.text}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function HomePage() {
  return (
    <>
      <Hero
        eyebrow="HR and sponsor compliance"
        title="Look after your people, and your licence."
        lead={`${brand.name} keeps your HR records and your sponsor duties in one calm place, so nothing important is missed.`}
        actions={[
          { label: SIGN_UP.label, href: SIGN_UP.href },
          { label: SIGN_IN.label, href: SIGN_IN.href, variant: "plain" },
        ]}
      >
        <TrustRow />
        <HeroShot className="mt-10 max-md:mt-40" />
      </Hero>

      <Section tone="raised" id="features">
        <SectionHeading
          title="Everything a small employer needs"
          lead="From the first contract to the last day, with the sponsor duties built in rather than bolted on."
        />
        <FeatureGrid features={FEATURES} className="mt-12" />
      </Section>

      <Band
        tone="page"
        eyebrow="Never caught out"
        title="Know what is due before it is due"
        lead="Dates that matter are tracked for you and brought to the top of your dashboard in good time."
        points={[
          "Visa and document expiry reminders, sent ahead of the date.",
          "A clear list of what to report, and by when.",
          "Everything is kept with its evidence, ready for an audit.",
        ]}
        media={<ReminderPreview />}
      />

      <Section tone="raised" id="faq">
        <SectionHeading title="Questions people ask" className="mb-10" />
        <Faq items={FAQ} />
        <StructuredData
          data={{
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: FAQ.map(({ question, answer }) => ({
              "@type": "Question",
              name: question,
              acceptedAnswer: { "@type": "Answer", text: answer },
            })),
          }}
        />
      </Section>

      <CtaBand
        title="Get your records in order today"
        lead="Start on the free plan. No card needed."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
