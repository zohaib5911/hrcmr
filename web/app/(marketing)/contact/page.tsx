import type { Metadata } from "next";

import { brand } from "@brand";

import { ContactForm } from "@/components/marketing/contact-form";
import { Section, SectionHeading } from "@/components/marketing/sections";

export const metadata: Metadata = {
  title: "Contact",
  description: `Get in touch with the ${brand.name} team. We reply within one working day.`,
};

export default function ContactPage() {
  return (
    <Section tone="raised">
      <SectionHeading
        level={1}
        title="Get in touch"
        lead="Tell us what you need and we will reply within one working day."
        className="mb-10"
      />
      <div className="mx-auto max-w-xl">
        <ContactForm />
      </div>
    </Section>
  );
}
