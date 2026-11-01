import type { Metadata } from "next";

import { HeadcountSlider, PricingCards } from "@/components/marketing/pricing";
import { Section, SectionHeading } from "@/components/marketing/sections";

import { HydrationFlag } from "../_components/hydration-flag";

export const metadata: Metadata = {
  title: "Design: marketing",
  robots: { index: false, follow: false },
};

/**
 * The marketing components that need prices, shown with the amounts the plan names (plan 8.15). The
 * real pricing page (T18.1) reads them from the Stripe price ids; here they are only to see the layout.
 * Development page only.
 */
export default function MarketingDesignPage() {
  return (
    <main>
      <HydrationFlag />
      <Section tone="page">
        <SectionHeading level={1} title="Simple pricing" lead="Layout demo with example amounts." />
        <SectionHeading title="Choose a plan" className="mt-16" />
        <div className="mt-10">
          <PricingCards
            plans={[
              {
                id: "annual",
                name: "Annual",
                price: "£50",
                cadence: "a year",
                description: "Everything, billed once a year.",
                features: ["All modules", "Sponsor compliance", "Email support"],
                action: { label: "Choose annual", href: "/login" },
              },
              {
                id: "ten-year",
                name: "10-year",
                price: "£240",
                cadence: "once, for ten years",
                description: "Pay once and forget about renewals.",
                features: ["All modules", "Sponsor compliance", "Email support"],
                action: { label: "Choose 10-year", href: "/login" },
                highlighted: true,
              },
            ]}
          />
        </div>
      </Section>
      <Section tone="raised">
        <SectionHeading title="Your price, per person" className="mb-10" />
        <HeadcountSlider
          plans={[
            { id: "annual", name: "Annual", amount: 50, years: 1 },
            { id: "ten-year", name: "10-year", amount: 240, years: 10 },
          ]}
        />
      </Section>
    </main>
  );
}
