import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import Link from "next/link";

import { brand } from "@brand";

import { Section, SectionHeading } from "@/components/marketing/sections";

export const metadata: Metadata = pageMetadata(
  "/accessibility",
  "Accessibility statement",
  `How accessible ${brand.name} is and how to tell us about a problem.`,
);

export default function AccessibilityPage() {
  return (
    <Section tone="raised">
      <SectionHeading level={1} title="Accessibility statement" className="mb-10" />
      <div className="text-body text-label mx-auto flex max-w-[45rem] flex-col gap-5">
        <p>
          We want {brand.name} to be usable by everyone. We aim to meet the Web Content
          Accessibility Guidelines (WCAG) 2.2, level AA, across the public website and the signed-in
          product.
        </p>
        <h2 className="text-title-3 font-semibold">What we do</h2>
        <ul className="text-label-secondary list-disc pl-6">
          <li>Every screen works with a keyboard alone, with a visible focus ring.</li>
          <li>Text and controls meet the AA contrast ratio in both light and dark themes.</li>
          <li>Pages use headings, landmarks and labels so screen readers can follow them.</li>
          <li>Motion is reduced for people who ask their device for less of it.</li>
          <li>State is never shown by colour alone; there is always a text label.</li>
          <li>We run automated checks on each page and test with a keyboard before release.</li>
        </ul>
        <h2 className="text-title-3 font-semibold">Known limits</h2>
        <p className="text-label-secondary">
          Automated checks do not find every problem. Some third-party parts, such as the Turnstile
          check on public forms, are outside our control. If one stops you, contact us and we will
          help another way.
        </p>
        <h2 className="text-title-3 font-semibold">Tell us about a problem</h2>
        <p className="text-label-secondary">
          If you find something hard to use, please{" "}
          <Link href="/contact" className="text-accent-text underline">
            contact us
          </Link>{" "}
          and tell us the page and what happened. We reply within one working day.
        </p>
        <p className="text-label-secondary">
          If you are not happy with our reply, you can contact the Equality Advisory and Support
          Service (EASS).
        </p>
      </div>
    </Section>
  );
}
