import { StructuredData } from "@/components/marketing/structured-data";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

import { brand } from "@brand";

import { Faq } from "@/components/marketing/faq";
import { HeadcountSlider, PricingCards } from "@/components/marketing/pricing";
import { CtaBand, Hero, Section, SectionHeading } from "@/components/marketing/sections";
import { PRICING, pounds } from "@/lib/marketing-pricing";
import { SIGN_UP } from "@/lib/marketing-nav";

export const metadata: Metadata = pageMetadata(
  "/pricing",
  "Pricing",
  `Two simple plans for ${brand.name}: an annual plan you can stop renewing at any time, or one payment for ten years.`,
);

const INCLUDED = [
  "One price, whatever your headcount",
  "Sponsor compliance reminders and reporting duties",
  "Right to work records",
  "Leave, attendance and rota",
  "Documents, policies and learning",
  "Recruitment and a public careers page",
  "Email support",
] as const;

const FAQ = [
  {
    question: "Why is it so cheap?",
    answer:
      "We keep the product small and focused, we do not run a sales team, and we would rather have many small employers than a few large ones. The price does not change with the number of people you employ.",
  },
  {
    question: "Does the price depend on how many people I employ?",
    answer: "No. Each plan has one price, so the price per person falls as you grow.",
  },
  {
    question: "What does the free plan include?",
    answer:
      "You can set up your company and look around. To add people and keep records you need a paid plan.",
  },
  {
    question: "How does cancelling work?",
    answer:
      "Cancel the annual plan at any time and it will not renew: you keep full access until the end of the year you paid for. The 10 year plan is a single payment that never renews. Payments are not refunded when you cancel.",
  },
  {
    question: "What happens when the plan ends?",
    answer:
      "Your account becomes read-only. You can still view and export everything. Renew to start editing again.",
  },
  {
    question: "Do prices include VAT?",
    answer: "Prices are shown before any VAT that applies. The total is shown before you pay.",
  },
] as const;

export default function PricingPage() {
  return (
    <>
      <Hero
        eyebrow="Pricing"
        title="Two plans. No surprises."
        lead="One price whatever your headcount. Stop renewing the annual plan whenever you like."
      />
      <Section tone="page" label="Plans" className="pt-0 md:pt-0">
        <PricingCards
          plans={[
            {
              id: "annual",
              name: "Annual",
              price: pounds(PRICING.annual.amount),
              cadence: "a year",
              description: "Pay each year and stop whenever you like.",
              features: INCLUDED,
              action: { label: SIGN_UP.label, href: SIGN_UP.href, variant: "tinted" },
            },
            {
              id: "ten-year",
              name: "10 year",
              price: pounds(PRICING.tenYear.amount),
              cadence: "once, for ten years",
              description: "Pay once and stop thinking about it.",
              features: INCLUDED,
              action: { label: SIGN_UP.label, href: SIGN_UP.href },
              highlighted: true,
            },
          ]}
        />
      </Section>
      <Section tone="raised" label="Price per person">
        <SectionHeading
          title="The more people, the less each costs"
          lead="Drag the slider to see the price per person, per year."
          className="mb-10"
        />
        <HeadcountSlider
          plans={[
            { id: "annual", name: "Annual", ...PRICING.annual },
            { id: "ten-year", name: "10 year", ...PRICING.tenYear },
          ]}
        />
      </Section>
      <Section tone="page" id="faq">
        <SectionHeading title="Questions about pricing" className="mb-10" />
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
        title="Start with the free plan"
        lead="Upgrade when you are ready."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
