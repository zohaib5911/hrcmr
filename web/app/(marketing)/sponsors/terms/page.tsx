import { Attribution } from "@/components/register/attribution";
import { Section, SectionHeading } from "@/components/marketing/sections";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata(
  "/sponsors/terms",
  "Sponsor register terms",
  "The terms for using the sponsor register pages.",
);

export default function Page() {
  return (
    <Section tone="page">
      <SectionHeading level={1} eyebrow="Sponsor register" title="Register terms" />
      <div className="text-body text-label mx-auto mt-8 flex max-w-3xl flex-col gap-4">
        <p>
          These pages are for information only and are not legal advice. The register on GOV.UK is
          the official record; check it before you rely on an entry.
        </p>
        <p>
          A licence does not mean the employer is hiring, and a listing is not a recommendation. Do
          not use these pages to contact people in bulk or to build marketing lists.
        </p>
        <p>
          If an entry is wrong, use the report form on the entry or on the methodology page. We
          correct our own mistakes; we cannot change the official register.
        </p>
        <Attribution />
      </div>
    </Section>
  );
}
