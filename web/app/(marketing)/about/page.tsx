import type { Metadata } from "next";

import { brand } from "@brand";

import { CtaBand, Hero, Section, SectionHeading } from "@/components/marketing/sections";
import { SIGN_UP } from "@/lib/marketing-nav";

export const metadata: Metadata = {
  title: "About",
  description: `Why ${brand.name} exists and how we think about it.`,
};

const PRINCIPLES = [
  {
    title: "Calm over clever",
    body: "A small employer should be able to open the product, see what matters today and close it again.",
  },
  {
    title: "Say what we know",
    body: "Where we give guidance we show the source and the date we checked it. We do not give legal advice.",
  },
  {
    title: "Keep it affordable",
    body: "A simple price that does not grow with your headcount, and your money back in the first two weeks.",
  },
] as const;

export default function AboutPage() {
  return (
    <>
      <Hero
        eyebrow="About"
        title="Built for employers who do not have an HR department"
        lead={`${brand.name} started from a simple idea: keeping good records and meeting sponsor duties should not need a specialist team.`}
      />
      <Section tone="raised" label="Principles">
        <div className="mx-auto grid max-w-4xl gap-8 md:grid-cols-3">
          {PRINCIPLES.map((principle) => (
            <div key={principle.title}>
              <h2 className="text-title-3 text-label font-semibold">{principle.title}</h2>
              <p className="text-body text-label-secondary mt-2">{principle.body}</p>
            </div>
          ))}
        </div>
      </Section>
      <Section tone="page">
        <SectionHeading
          title="Talk to us"
          lead="We are a small team and we read every message. Use the contact page and we will reply within one working day."
        />
      </Section>
      <CtaBand
        title="See if it fits your business"
        lead="Start on the free plan. No card needed."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
